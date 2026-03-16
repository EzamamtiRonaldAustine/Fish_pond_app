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
        
        if config.get('DATABASE_URL'):
            conn = psycopg2.connect(config['DATABASE_URL'])
        else:
            conn = psycopg2.connect(
                dbname=config.get('DB_NAME'),
                user=config.get('DB_USER'),
                password=config.get('DB_PASSWORD'),
                host=config.get('DB_HOST'),
                port=config.get('DB_PORT'),
            )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        return None