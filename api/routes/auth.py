# api/routes/auth.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from ..database import get_db_connection
from psycopg2.extras import RealDictCursor
from datetime import datetime
import logging
from ..utils import get_user_from_token, require_role

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    """Enhanced login with organization context."""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT u.*, o.name as organization_name, o.subscription_tier
            FROM users u
            LEFT JOIN organizations o ON u.organization_id = o.id
            WHERE u.username = %s AND u.is_active = TRUE
        """, (username,))
        user = cur.fetchone()
        
        if not user:
            logger.warning(f"Login attempt failed - User not found: {username}")
            cur.close()
            conn.close()
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check password
        password_valid = False
        if user.get('password_hash'):
            password_hash = user.get('password_hash')
            if password_hash.startswith('pbkdf2:'):
                try:
                    password_valid = check_password_hash(password_hash, password)
                except Exception as hash_error:
                    logger.error(f"Hash verification error: {hash_error}")
                    password_valid = False
            else:
                # Legacy plain text
                password_valid = (password_hash == password)
                if password_valid:
                    # Auto-upgrade
                    new_hash = generate_password_hash(password, method='pbkdf2:sha256')
                    cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", 
                               (new_hash, user['id']))
                    conn.commit()
        
        if password_valid:
            logger.info(f"Login successful for user: {username}")
            
            # Update last login
            cur.execute("UPDATE users SET last_login = %s WHERE id = %s", 
                       (datetime.now(), user['id']))
            conn.commit()
            
            # Create access token with additional claims
            access_token = create_access_token(
                identity=username,
                additional_claims={
                    'role': user['role'],
                    'organization_id': user['organization_id']
                }
            )
            
            cur.close()
            conn.close()
            
            return jsonify({
                'access_token': access_token,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'full_name': user['full_name'],
                    'role': user['role'],
                    'organization_id': user['organization_id'],
                    'organization_name': user['organization_name'],
                    'subscription_tier': user['subscription_tier']
                }
            }), 200
        else:
            logger.warning(f"Login failed - Invalid password for user: {username}")
            cur.close()
            conn.close()
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user info."""
    user = get_user_from_token()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get organization info
    conn = get_db_connection()
    if conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT name, subscription_tier 
            FROM organizations 
            WHERE id = %s
        """, (user['organization_id'],))
        org = cur.fetchone()
        cur.close()
        conn.close()
        
        if org:
            user['organization_name'] = org['name']
            user['subscription_tier'] = org['subscription_tier']
    
    return jsonify({'user': user}), 200

@auth_bp.route('/device-status', methods=['GET'])
@jwt_required()
def check_device_status():
    """Check if user has any devices configured."""
    try:
        user = get_user_from_token()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if user has devices
        cur.execute("""
            SELECT user_has_devices(%s) as has_devices
        """, (user['id'],))
        result = cur.fetchone()
        
        # Get device count and list based on user role
        devices = []
        device_count = 0
        
        if user['role'] == 'admin':
            # Admins see all devices in their organization
            cur.execute("""
                SELECT 
                    d.*,
                    sr.ec, sr.nitrogen, sr.phosphorus, sr.turbidity,
                    u.username as owner_username, u.full_name as owner_name
                FROM devices d
                LEFT JOIN users u ON d.created_by = u.id
                LEFT JOIN LATERAL (
                    SELECT ec, nitrogen, phosphorus, turbidity
                    FROM sensor_readings
                    WHERE device_id = d.id
                    ORDER BY timestamp DESC
                    LIMIT 1
                ) sr ON true
                WHERE d.organization_id = %s
                ORDER BY d.created_at DESC
            """, (user['organization_id'],))
            devices = cur.fetchall()
            device_count = len(devices)
        else:
            # Farmers only see devices they own or have explicit permissions for (via v_user_device_access view)
            cur.execute("""
                SELECT 
                    d.*,
                    sr.ec,
                    sr.nitrogen,
                    sr.phosphorus,
                    sr.turbidity,
                    u.username as owner_username,
                    u.full_name as owner_name
                FROM v_user_device_access v
                JOIN devices d ON v.device_id = d.id
                LEFT JOIN users u ON d.created_by = u.id
                LEFT JOIN LATERAL (
                    SELECT ec, nitrogen, phosphorus, turbidity
                    FROM sensor_readings
                    WHERE device_id = d.id
                    ORDER BY timestamp DESC
                    LIMIT 1
                ) sr ON true
                WHERE v.user_id = %s
                ORDER BY d.created_at DESC
            """, (user['id'],))
            devices = cur.fetchall()
            device_count = len(devices)
        
        cur.close()
        conn.close()
        
        return jsonify({
            'has_devices': result['has_devices'],
            'device_count': device_count,
            'user_role': user['role']
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking device status: {e}")
        return jsonify({'error': 'Failed to check device status'}), 500

@auth_bp.route('/register', methods=['POST'])
@require_role('admin')
def register_user():
    """Create a new user (admin only)."""
    try:
        user = get_user_from_token()
        data = request.get_json()
        
        # Validate required fields
        required = ['username', 'password', 'email', 'full_name', 'role']
        if not all(field in data for field in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if data['role'] not in ['admin', 'farmer']:
            return jsonify({'error': 'Invalid role. Must be admin or farmer'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        password_hash = generate_password_hash(data['password'], method='pbkdf2:sha256')
        org_id = data.get('organization_id', user['organization_id'])
        
        cur.execute("""
            INSERT INTO users (
                username, password_hash, email, full_name, 
                role, organization_id, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, username, email, full_name, role, organization_id
        """, (
            data['username'],
            password_hash,
            data['email'],
            data['full_name'],
            data['role'],
            org_id
        ))
        
        new_user = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'message': 'User created successfully',
            'user': dict(new_user)
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({'error': 'Failed to create user'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password."""
    try:
        user = get_user_from_token()
        data = request.get_json()
        
        if not data.get('old_password') or not data.get('new_password'):
            return jsonify({'error': 'Old and new passwords required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (user['id'],))
        result = cur.fetchone()
        
        if not result or not check_password_hash(result['password_hash'], data['old_password']):
            cur.close()
            conn.close()
            return jsonify({'error': 'Invalid old password'}), 401
        
        new_hash = generate_password_hash(data['new_password'], method='pbkdf2:sha256')
        cur.execute("""
            UPDATE users 
            SET password_hash = %s 
            WHERE id = %s
        """, (new_hash, user['id']))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'message': 'Password updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return jsonify({'error': 'Failed to change password'}), 500

@auth_bp.route('/signup', methods=['POST'])
def public_signup():
    """Public self-registration for farmers."""
    try:
        data = request.get_json()
        required = ['username', 'password', 'email', 'full_name', 'organization_id']
        if not all(field in data for field in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        password_hash = generate_password_hash(data['password'], method='pbkdf2:sha256')
        
        # Check org existence
        cur.execute("SELECT id FROM organizations WHERE id = %s", (data['organization_id'],))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Invalid organization ID'}), 400
        
        cur.execute("""
            INSERT INTO users (
                username, password_hash, email, full_name, 
                role, organization_id, created_at
            ) VALUES (%s, %s, %s, %s, 'farmer', %s, NOW())
            RETURNING id, username, email, full_name, role, organization_id
        """, (
            data['username'],
            password_hash,
            data['email'],
            data['full_name'],
            data['organization_id']
        ))
        
        new_user = cur.fetchone()
        conn.commit()
        
        access_token = create_access_token(
            identity=new_user['username'],
            additional_claims={
                'role': new_user['role'],
                'organization_id': new_user['organization_id']
            }
        )
        
        cur.close()
        conn.close()
        
        return jsonify({
            'message': 'Registration successful',
            'access_token': access_token,
            'user': dict(new_user)
        }), 201
        
    except Exception as e:
        logger.error(f"Error during signup: {e}")
        return jsonify({'error': 'Registration failed'}), 500