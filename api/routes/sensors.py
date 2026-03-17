# api/routes/sensors.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import logging
import os
from ..database import get_db_connection
from ..utils import get_user_from_token, check_device_access
from ..predict import predict_water_quality

sensors_bp = Blueprint('sensors', __name__)
logger = logging.getLogger(__name__)

# Registration at /api -> routes start with /devices, /current-readings, or /sensors


# ─────────────────────────────────────────────────────────────────────────────
# Raspberry Pi ingest: POST /api/sensors/readings
# ─────────────────────────────────────────────────────────────────────────────

def _verify_device_key() -> bool:
    """Validate X-Device-Key header against env var DEVICE_API_KEY."""
    expected = os.environ.get("DEVICE_API_KEY", "")
    return bool(expected) and expected == request.headers.get("X-Device-Key", "")


@sensors_bp.route('/sensors/readings', methods=['POST'])
def ingest_sensor_reading():
    """
    Receive a sensor snapshot from the Raspberry Pi hardware agent.

    Authentication: X-Device-Key header (pre-shared secret).

    Request body (JSON)
    -------------------
    {
        "device_id":      1,
        "temperature":    26.2,
        "ph":             7.1,
        "ec":             850.0,
        "nitrogen":       112.0,
        "phosphorus":     98.0,
        "turbidity":      0,
        "quality_score":  15,
        "quality_status": "GOOD",
        "alerts":         []
    }

    Response 201
    ------------
    { "message": "Reading stored", "reading_id": 42 }
    """
    if not _verify_device_key():
        return jsonify({"error": "Invalid or missing device key"}), 401

    body = request.get_json(silent=True) or {}
    device_id = body.get("device_id")
    quality_status = body.get("quality_status", "GOOD").upper()
    
    if not device_id:
        return jsonify({"error": "device_id is required"}), 400

    # ── AI Assessment (ML 2 Integration) ─────────────────────────
    try:
        if all(k in body for k in ("temperature", "ph", "nitrogen", "phosphorus")):
            # Nitrogen naturally routes to 'nitrite' in predict.py adapter
            assessment = predict_water_quality(
                temperature=float(body["temperature"]),
                ph=float(body["ph"]),
                nitrite=float(body["nitrogen"]),  
                phosphorus=float(body["phosphorus"])
            )
            # Store AI Assessment separately - DO NOT overwrite hardware status
            ai_label = assessment.get("quality_label", "").upper()
            if ai_label:
                logger.info(f"AI Assessment: ML assessed {ai_label} (Hardware reported {body.get('quality_status')})")
    except Exception as ml_err:
        logger.error(f"ML Inference failed on sensor ingest: {ml_err}")
    # ─────────────────────────────────────────────────────────────

    # Enforce known states (note: Excellent replaces Good in ML terminology, but DB expects Good/Warning/Critical)
    # Map the ML labels back to the UI / DB standard expectations to prevent DB constraint errors
    if quality_status == "EXCELLENT":
        quality_status = "GOOD"
    elif quality_status == "POOR":
        quality_status = "CRITICAL"
        
    if quality_status not in ("GOOD", "WARNING", "CRITICAL"):
        quality_status = "GOOD"

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Insert sensor reading
        cur.execute(
            """
            INSERT INTO sensor_readings
                (device_id, temperature, ph, ec, nitrogen, phosphorus,
                 turbidity, quality_score, quality_status, ai_quality_label)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                device_id,
                body.get("temperature"),
                body.get("ph"),
                body.get("ec"),
                body.get("nitrogen"),
                body.get("phosphorus"),
                bool(body.get("turbidity")),
                body.get("quality_score"),
                quality_status,
                ai_label if 'ai_label' in locals() else None,
            ),
        )
        row = cur.fetchone()
        reading_id = row["id"] if row else None

        # Auto-create an alert log entry for CRITICAL readings
        if quality_status == "CRITICAL" and body.get("alerts"):
            alert_message = "; ".join(body["alerts"][:3])
            cur.execute(
                """
                INSERT INTO alerts
                    (device_id, alert_type, severity, message)
                VALUES (%s, %s, %s, %s)
                """,
                (device_id, "water_quality", "CRITICAL", alert_message[:500]),
            )

        # Bump device last_seen timestamp
        cur.execute(
            "UPDATE devices SET last_seen = NOW() WHERE id = %s",
            (device_id,),
        )

        conn.commit()
        cur.close()
        conn.close()

        logger.info(
            f"Sensor reading #{reading_id} stored for device {device_id} "
            f"(status={quality_status})"
        )
        return jsonify({"message": "Reading stored", "reading_id": reading_id}), 201

    except Exception as exc:
        logger.error(f"Error storing sensor reading: {exc}")
        return jsonify({"error": "Failed to store reading"}), 500
# Registration at /api -> routes start with /devices or /current-readings

@sensors_bp.route('/devices/<int:device_id>/current-readings', methods=['GET'])
@jwt_required(optional=True)
def get_device_current_readings(device_id):
    """Get latest readings for a specific device."""
    try:
        current_user = get_jwt_identity()
        if current_user:
            user = get_user_from_token()
            if user and user['role'] != 'admin' and not check_device_access(user['id'], device_id):
                return jsonify({'error': 'Access denied'}), 403
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT temperature, ph, ec, nitrogen, phosphorus, turbidity,
                   quality_status, quality_score, timestamp, ai_quality_label
            FROM sensor_readings
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            return jsonify({'error': 'No readings found'}), 404
        
        return jsonify({
            'temperature': float(row['temperature']) if row['temperature'] is not None else None,
            'ph': float(row['ph']) if row['ph'] is not None else None,
            'ec': float(row['ec']) if row['ec'] is not None else None,
            'nitrogen': float(row['nitrogen']) if row['nitrogen'] is not None else None,
            'phosphorus': float(row['phosphorus']) if row['phosphorus'] is not None else None,
            'turbidity': bool(row['turbidity']) if row['turbidity'] is not None else None,
            'status': row['quality_status'],
            'ai_label': row.get('ai_quality_label'),
            'score': row['quality_score'],
            'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting current readings: {e}")
        return jsonify({'error': 'Failed to retrieve readings'}), 500


@sensors_bp.route('/current-readings', methods=['GET'])
@jwt_required(optional=True)
def get_current_readings():
    """Get latest readings (legacy endpoint)."""
    try:
        user = None
        current_user = get_jwt_identity()
        if current_user:
            user = get_user_from_token()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if user and user['role'] == 'admin':
            cur.execute("SELECT id FROM devices WHERE status = 'active' ORDER BY id LIMIT 1")
        elif user:
            cur.execute("""
                SELECT id FROM devices 
                WHERE organization_id = %s AND status = 'active' 
                ORDER BY id LIMIT 1
            """, (user['organization_id'],))
        else:
            cur.execute("SELECT id FROM devices WHERE device_id = 'LEGACY-DEVICE-001'")
        
        device = cur.fetchone()
        
        if not device:
            cur.close()
            conn.close()
            return jsonify({'error': 'No device found'}), 404
            
        cur.close()
        conn.close()
        # Redirect to device specific handler logic
        return get_device_current_readings(device['id'])
        
    except Exception as e:
        logger.error(f"Error getting current readings: {e}")
        return jsonify({'error': 'Failed to retrieve readings'}), 500


@sensors_bp.route('/devices/<int:device_id>/historical/<parameter>', methods=['GET'])
@jwt_required(optional=True)
def get_device_historical(device_id, parameter):
    """Get historical data for specific device and parameter."""
    try:
        current_user = get_jwt_identity()
        if current_user:
            user = get_user_from_token()
            if user and user['role'] != 'admin' and not check_device_access(user['id'], device_id):
                return jsonify({'error': 'Access denied'}), 403
        
        period = request.args.get('period', '24h')
        limit = int(request.args.get('limit', 100))
        
        hours = {'24h': 24, '7d': 168, '30d': 720}.get(period, 24)
        start_time = datetime.now() - timedelta(hours=hours)
        
        valid_params = ['temperature', 'ph', 'ec', 'nitrogen', 'phosphorus', 'turbidity', 'ai_quality_label', 'quality_status']
        if parameter not in valid_params:
            return jsonify({'error': f'Invalid parameter'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT timestamp, {parameter}
            FROM sensor_readings
            WHERE device_id = %s 
              AND timestamp >= %s 
              AND {parameter} IS NOT NULL
            ORDER BY timestamp ASC
            LIMIT %s
        """, (device_id, start_time, limit))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        is_string_param = parameter in ['ai_quality_label', 'quality_status']
        
        data = [{
            'timestamp': row['timestamp'].isoformat(),
            'value': row[parameter] if is_string_param else (float(row[parameter]) if row[parameter] is not None else None)
        } for row in rows]
        
        return jsonify({
            'device_id': device_id,
            'parameter': parameter,
            'period': period,
            'data_points': len(data),
            'data': data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting historical data: {e}")
        return jsonify({'error': 'Failed to retrieve historical data'}), 500


@sensors_bp.route('/historical/<parameter>', methods=['GET'])
@jwt_required(optional=True)
def get_historical(parameter):
    """Legacy endpoint - redirects to first accessible device."""
    user = None
    current_user = get_jwt_identity()
    if current_user:
        user = get_user_from_token()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database unavailable'}), 503
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if user and user['role'] == 'admin':
        cur.execute("SELECT id FROM devices WHERE status = 'active' ORDER BY id LIMIT 1")
    elif user:
        cur.execute("""
            SELECT id FROM devices 
            WHERE organization_id = %s AND status = 'active' 
            ORDER BY id LIMIT 1
        """, (user['organization_id'],))
    else:
        cur.execute("SELECT id FROM devices WHERE device_id = 'LEGACY-DEVICE-001'")
    
    device = cur.fetchone()
    cur.close()
    conn.close()
    
    if not device:
        return jsonify({'error': 'No device found'}), 404
    
    return get_device_historical(device['id'], parameter)
