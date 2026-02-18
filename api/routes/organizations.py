# api/routes/organizations.py
from flask import Blueprint, jsonify
from psycopg2.extras import RealDictCursor
import logging
from ..database import get_db_connection
from ..utils import require_role

organizations_bp = Blueprint('organizations', __name__)
logger = logging.getLogger(__name__)

# Registration at /api

@organizations_bp.route('/organizations', methods=['GET'])
@require_role('admin')
def get_organizations():
    """Get all organizations (admin only)."""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT o.*, 
                   COUNT(DISTINCT d.id) as device_count,
                   COUNT(DISTINCT u.id) as user_count
            FROM organizations o
            LEFT JOIN devices d ON d.organization_id = o.id
            LEFT JOIN users u ON u.organization_id = o.id AND u.is_active = TRUE
            WHERE o.is_active = TRUE
            GROUP BY o.id
            ORDER BY o.created_at DESC
        """)
        
        orgs = cur.fetchall()
        cur.close()
        conn.close()
        
        orgs_list = []
        for org in orgs:
            org_dict = dict(org)
            if org_dict.get('created_at'):
                org_dict['created_at'] = org_dict['created_at'].isoformat()
            orgs_list.append(org_dict)
        
        return jsonify({'organizations': orgs_list}), 200
        
    except Exception as e:
        logger.error(f"Error getting organizations: {e}")
        return jsonify({'error': 'Failed to retrieve organizations'}), 500


@organizations_bp.route('/organizations/list', methods=['GET'])
def get_organizations_list():
    """Get list of organizations for signup dropdown (public access)."""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 503
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, subscription_tier
            FROM organizations
            WHERE is_active = TRUE
            ORDER BY name ASC
        """)
        
        orgs = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({'organizations': [dict(org) for org in orgs]}), 200
        
    except Exception as e:
        logger.error(f"Error getting organizations: {e}")
        return jsonify({'error': 'Failed to retrieve organizations'}), 500
