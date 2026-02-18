# api/routes/alerts.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from psycopg2.extras import RealDictCursor
from datetime import datetime
import logging
from ..database import get_db_connection
from ..utils import get_user_from_token, require_role, check_device_access

alerts_bp = Blueprint('alerts', __name__)
logger = logging.getLogger(__name__)

# Registration at /api

@alerts_bp.route('/devices/<int:device_id>/alerts', methods=['GET'])
@jwt_required(optional=True)
def get_device_alerts(device_id):
    """Get alerts for specific device."""
    try:
        user = get_user_from_token()
        if user and user['role'] != 'admin' and not check_device_access(user['id'], device_id):
            return jsonify({'error': 'Access denied'}), 403
        
        limit = int(request.args.get('limit', 20))
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, timestamp, alert_type, severity, message,
                   acknowledged, acknowledged_at
            FROM alerts
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """, (device_id, limit))
        
        alerts = cur.fetchall()
        cur.close()
        conn.close()
        
        alerts_list = []
        for alert in alerts:
            alert_dict = dict(alert)
            if alert_dict.get('timestamp'):
                alert_dict['timestamp'] = alert_dict['timestamp'].isoformat()
            if alert_dict.get('acknowledged_at'):
                alert_dict['acknowledged_at'] = alert_dict['acknowledged_at'].isoformat()
            alerts_list.append(alert_dict)
        
        return jsonify({'alerts': alerts_list}), 200
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return jsonify({'error': 'Failed to retrieve alerts'}), 500


@alerts_bp.route('/alerts', methods=['GET'])
@jwt_required(optional=True)
def get_alerts():
    """Legacy alerts endpoint."""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503

        # For legacy, assume default device if not specified or just pick one
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id FROM devices WHERE device_id = 'LEGACY-DEVICE-001'")
        device = cur.fetchone()
        cur.close()
        conn.close()
        
        if device:
            return get_device_alerts(device['id'])
        return jsonify({'alerts': []}), 200
    except Exception as e:
         logger.error(f"Error getting legacy alerts: {e}")
         return jsonify({'error': 'Failed to retrieve alerts'}), 500

@alerts_bp.route('/alerts/summary', methods=['GET'])
@require_role('admin')
def get_alert_summary():
    """Get alert summary grouped by device (admin only)."""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM device_alert_summary
            ORDER BY unacknowledged_count DESC, last_alert_time DESC
        """)
        
        summaries = cur.fetchall()
        cur.close()
        conn.close()
        
        summary_list = []
        for summary in summaries:
            summary_dict = dict(summary)
            if summary_dict.get('last_alert_time'):
                summary_dict['last_alert_time'] = summary_dict['last_alert_time'].isoformat()
            summary_list.append(summary_dict)
        
        return jsonify({'alert_summaries': summary_list}), 200
        
    except Exception as e:
        logger.error(f"Error getting alert summary: {e}")
        return jsonify({'error': 'Failed to retrieve alert summary'}), 500


@alerts_bp.route('/alerts/acknowledge/<int:alert_id>', methods=['POST'])
@jwt_required()
def acknowledge_alert(alert_id):
    """Acknowledge an alert."""
    try:
        user = get_user_from_token()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if alert exists and user has access
        cur.execute("""
            SELECT a.*, d.organization_id
            FROM alerts a
            JOIN devices d ON a.device_id = d.id
            WHERE a.id = %s
        """, (alert_id,))
        
        alert = cur.fetchone()
        
        if not alert:
            cur.close()
            conn.close()
            return jsonify({'error': 'Alert not found'}), 404
        
        # Check access
        if user['role'] != 'admin' and alert['organization_id'] != user['organization_id']:
            cur.close()
            conn.close()
            return jsonify({'error': 'Access denied'}), 403
        
        # Acknowledge the alert
        cur.execute("""
            UPDATE alerts
            SET acknowledged = TRUE,
                acknowledged_at = NOW(),
                acknowledged_by = %s
            WHERE id = %s
        """, (user['id'], alert_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Alert {alert_id} acknowledged by {user['username']}")
        
        return jsonify({'message': 'Alert acknowledged successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        return jsonify({'error': 'Failed to acknowledge alert'}), 500
