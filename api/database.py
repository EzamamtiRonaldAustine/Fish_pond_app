# api/database.py
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def get_db_connection():
    """Create and return a database connection."""
    try:
        config = current_app.config
        conn = psycopg2.connect(
            dbname=config['DB_NAME'],
            user=config['DB_USER'],
            password=config['DB_PASSWORD'],
            host=config['DB_HOST'],
            port=config['DB_PORT'],
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        return None