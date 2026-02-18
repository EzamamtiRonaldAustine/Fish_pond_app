# api/routes/devices.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from psycopg2.extras import RealDictCursor
import logging
from ..database import get_db_connection
from ..utils import get_user_from_token, check_device_access

devices_bp = Blueprint('devices', __name__)
logger = logging.getLogger(__name__)

# Registration at /api -> routes start with /devices

@devices_bp.route('/devices', methods=['GET'])
@jwt_required()
def get_devices():
    """Get all devices user has access to with owner information."""
    try:
        user = get_user_from_token()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if user['role'] == 'admin':
            cur.execute("""
                SELECT d.*, 
                       o.name as organization_name,
                       u.username as owner_username,
                       u.full_name as owner_name,
                       sr.temperature, sr.ph, sr.quality_status
                FROM devices d
                LEFT JOIN organizations o ON d.organization_id = o.id
                LEFT JOIN users u ON d.created_by = u.id
                LEFT JOIN LATERAL (
                    SELECT temperature, ph, quality_status
                    FROM sensor_readings
                    WHERE device_id = d.id
                    ORDER BY timestamp DESC
                    LIMIT 1
                ) sr ON true
                ORDER BY d.created_at DESC
            """)
        else:
            cur.execute("""
                SELECT d.*, 
                       o.name as organization_name,
                       u.username as owner_username,
                       u.full_name as owner_name,
                       sr.temperature, sr.ph, sr.quality_status
                FROM devices d
                LEFT JOIN organizations o ON d.organization_id = o.id
                LEFT JOIN users u ON d.created_by = u.id
                LEFT JOIN LATERAL (
                    SELECT temperature, ph, quality_status
                    FROM sensor_readings
                    WHERE device_id = d.id
                    ORDER BY timestamp DESC
                    LIMIT 1
                ) sr ON true
                WHERE d.organization_id = %s
                ORDER BY d.created_at DESC
            """, (user['organization_id'],))
        
        devices = cur.fetchall()
        cur.close()
        conn.close()
        
        devices_list = []
        for device in devices:
            dev_dict = dict(device)
            if dev_dict.get('created_at'):
                dev_dict['created_at'] = dev_dict['created_at'].isoformat()
            if dev_dict.get('last_seen'):
                dev_dict['last_seen'] = dev_dict['last_seen'].isoformat()
            if dev_dict.get('last_reading_at'):
                dev_dict['last_reading_at'] = dev_dict['last_reading_at'].isoformat()
            devices_list.append(dev_dict)
        
        return jsonify({'devices': devices_list}), 200
        
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return jsonify({'error': 'Failed to retrieve devices'}), 500

@devices_bp.route('/devices/<int:device_id>', methods=['GET'])
@jwt_required()
def get_device(device_id):
    """Get specific device details."""
    try:
        user = get_user_from_token()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if user['role'] != 'admin' and not check_device_access(user['id'], device_id):
            return jsonify({'error': 'Access denied'}), 403
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT d.*, o.name as organization_name
            FROM devices d
            LEFT JOIN organizations o ON d.organization_id = o.id
            WHERE d.id = %s
        """, (device_id,))
        
        device = cur.fetchone()
        cur.close()
        conn.close()
        
        if not device:
            return jsonify({'error': 'Device not found'}), 404
            
        device_dict = dict(device)
        if device_dict.get('created_at'):
            device_dict['created_at'] = device_dict['created_at'].isoformat()
        if device_dict.get('last_seen'):
            device_dict['last_seen'] = device_dict['last_seen'].isoformat()
        
        return jsonify({'device': device_dict}), 200
        
    except Exception as e:
        logger.error(f"Error getting device: {e}")
        return jsonify({'error': 'Failed to retrieve device'}), 500

@devices_bp.route('/devices', methods=['POST'])
@jwt_required()
def create_device():
    """Create new device (farmer/admin only)."""
    try:
        user = get_user_from_token()
        if not user or user['role'] not in ['admin', 'farmer']:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        data = request.get_json()
        required = ['device_id', 'name']
        if not all(field in data for field in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        org_id = data.get('organization_id', user['organization_id'])
        if user['role'] != 'admin' and org_id != user['organization_id']:
            return jsonify({'error': 'Cannot create device for other organization'}), 403
        
        cur.execute("""
            INSERT INTO devices (
                device_id, name, description, organization_id,
                raspberry_pi_ip, raspberry_pi_mac, location_description,
                created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, device_id, name
        """, (
            data['device_id'],
            data['name'],
            data.get('description'),
            org_id,
            data.get('raspberry_pi_ip'),
            data.get('raspberry_pi_mac'),
            data.get('location_description'),
            user['id']
        ))
        
        new_device = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'message': 'Device created successfully',
            'device': dict(new_device)
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating device: {e}")
        return jsonify({'error': 'Failed to create device'}), 500
