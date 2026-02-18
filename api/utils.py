# api/utils.py
import logging
from functools import wraps
from flask import jsonify, current_app
from flask_jwt_extended import get_jwt_identity, jwt_required
from psycopg2.extras import RealDictCursor
from .database import get_db_connection

logger = logging.getLogger(__name__)

def get_user_from_token():
    """Get full user object from JWT token."""
    username = get_jwt_identity()
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, username, email, full_name, role, organization_id
            FROM users 
            WHERE username = %s AND is_active = TRUE
        """, (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return dict(user) if user else None
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return None


def check_device_access(user_id, device_id, required_level='viewer'):
    """Check if user has access to a specific device."""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_has_device_access(%s, %s, %s)
        """, (user_id, device_id, required_level))
        
        # Determine if the function call returns a tuple or scalar
        # Assuming the robust SQL approach, it returns a boolean
        result = cur.fetchone()
        has_access = result[0] if result else False
        
        cur.close()
        conn.close()
        return has_access
    except Exception as e:
        logger.error(f"Error checking device access: {e}")
        return False


def require_role(*allowed_roles):
    """Decorator to restrict endpoint to specific roles."""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user = get_user_from_token()
            if not user or user['role'] not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
