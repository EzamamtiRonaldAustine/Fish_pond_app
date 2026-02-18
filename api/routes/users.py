# api/routes/users.py
from flask import Blueprint, jsonify
from psycopg2.extras import RealDictCursor
import logging
from ..database import get_db_connection
from ..utils import get_user_from_token, require_role

# Notice the blueprint name is 'users_bp' but registration URL prefix in __init__.py is '/api'
# So routes here should be mounted at '/users', '/users/<id>', etc.
# Wait, checking __init__.py provided by user:
# app.register_blueprint(users_bp, url_prefix='/api')
# But the big file has routes like /api/users.
# So here we define route '/users'.

users_bp = Blueprint('users', __name__)
logger = logging.getLogger(__name__)

@users_bp.route('/users', methods=['GET'])
@require_role('admin')
def get_all_users():
    """Get all users with their device counts (admin only)."""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Assuming user_device_summary view exists as per big file logic usage
        # Or fall back to simple select if view not present
        try:
            cur.execute("""
                SELECT * FROM user_device_summary
                ORDER BY created_at DESC
            """)
        except Exception:
            # Fallback if view doesn't exist
            conn.rollback()
            cur.execute("SELECT * FROM users ORDER BY created_at DESC")
        
        users = cur.fetchall()
        cur.close()
        conn.close()
        
        users_list = []
        for user in users:
            user_dict = dict(user)
            if user_dict.get('created_at'):
                user_dict['created_at'] = user_dict['created_at'].isoformat()
            if user_dict.get('last_login'):
                user_dict['last_login'] = user_dict['last_login'].isoformat()
            users_list.append(user_dict)
        
        return jsonify({'users': users_list}), 200
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'error': 'Failed to retrieve users'}), 500

@users_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@require_role('admin')
def soft_delete_user(user_id):
    """Soft delete a user (admin only)."""
    try:
        admin_user = get_user_from_token()
        if not admin_user:
            return jsonify({'error': 'Admin not found'}), 404
        
        if admin_user['id'] == user_id:
            return jsonify({'error': 'Cannot delete yourself'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT username, full_name FROM users WHERE id = %s", (user_id,))
        user_to_delete = cur.fetchone()
        
        if not user_to_delete:
            cur.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Soft delete procedure/function call
        try:
            cur.execute("SELECT soft_delete_user(%s, %s)", (user_id, admin_user['id']))
            success = cur.fetchone()[0]
        except Exception:
            conn.rollback()
            # Fallback manual soft delete if function missing
            cur.execute("""
                UPDATE users SET is_active = FALSE, deleted_at = NOW(), deleted_by = %s 
                WHERE id = %s
            """, (admin_user['id'], user_id))
            success = True
        
        conn.commit()
        cur.close()
        conn.close()
        
        if success:
            logger.info(f"User {user_to_delete['username']} soft-deleted by admin {admin_user['username']}")
            return jsonify({
                'message': f"User '{user_to_delete['full_name']}' marked for deletion.",
                'deleted_user': user_to_delete['username']
            }), 200
        else:
            return jsonify({'error': 'User already deleted or not found'}), 400
        
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return jsonify({'error': 'Failed to delete user'}), 500

@users_bp.route('/users/<int:user_id>/restore', methods=['POST'])
@require_role('admin')
def restore_deleted_user(user_id):
    """Restore a soft-deleted user (admin only)."""
    try:
        admin_user = get_user_from_token()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cur.execute("SELECT restore_user(%s)", (user_id,))
            success = cur.fetchone()[0]
        except Exception:
            conn.rollback()
            # Fallback manual restore
            cur.execute("UPDATE users SET is_active = TRUE, deleted_at = NULL, deleted_by = NULL WHERE id = %s", (user_id,))
            success = True
        
        if success:
            cur.execute("SELECT username, full_name FROM users WHERE id = %s", (user_id,))
            restored_user = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"User {restored_user['username']} restored by admin {admin_user['username']}")
            return jsonify({
                'message': f"User '{restored_user['full_name']}' successfully restored",
                'restored_user': restored_user['username']
            }), 200
        else:
            cur.close()
            conn.close()
            return jsonify({'error': 'User not found or not deleted'}), 400
        
    except Exception as e:
        logger.error(f"Error restoring user: {e}")
        return jsonify({'error': 'Failed to restore user'}), 500

@users_bp.route('/users/deleted', methods=['GET'])
@require_role('admin')
def get_deleted_users():
    """Get list of soft-deleted users (admin only)."""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT u.id, u.username, u.email, u.full_name, u.role,
                   u.deleted_at, u.deleted_by
            FROM users u
            WHERE u.deleted_at IS NOT NULL
            ORDER BY u.deleted_at DESC
        """)
        
        deleted_users = cur.fetchall()
        cur.close()
        conn.close()
        
        users_list = []
        for user in deleted_users:
            user_dict = dict(user)
            if user_dict.get('deleted_at'):
                user_dict['deleted_at'] = user_dict['deleted_at'].isoformat()
            users_list.append(user_dict)
        
        return jsonify({'deleted_users': users_list}), 200
        
    except Exception as e:
        logger.error(f"Error getting deleted users: {e}")
        return jsonify({'error': 'Failed to retrieve deleted users'}), 500
