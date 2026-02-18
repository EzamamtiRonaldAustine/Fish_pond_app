# api/routes/health.py
from flask import Blueprint, jsonify
from datetime import datetime
from ..database import get_db_connection

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Health check with database schema version."""
    try:
        conn = get_db_connection()
        db_status = 'connected' if conn else 'disconnected'
        
        # Check if v2 schema exists
        schema_version = 'v1'
        if conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'devices'
                )
            """)
            has_v2 = cur.fetchone()[0]
            schema_version = 'v2' if has_v2 else 'v1'
            cur.close()
            conn.close()
        
        return jsonify({
            'status': 'healthy',
            'database': db_status,
            'schema_version': schema_version,
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
