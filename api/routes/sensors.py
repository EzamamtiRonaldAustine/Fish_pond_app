# api/routes/sensors.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import logging
from ..database import get_db_connection
from ..utils import get_user_from_token, check_device_access

sensors_bp = Blueprint('sensors', __name__)
logger = logging.getLogger(__name__)

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
                   quality_status, quality_score, timestamp
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
        
        valid_params = ['temperature', 'ph', 'ec', 'nitrogen', 'phosphorus', 'turbidity']
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
        
        data = [{
            'timestamp': row['timestamp'].isoformat(),
            'value': float(row[parameter]) if row[parameter] is not None else None
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
