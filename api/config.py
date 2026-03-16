# api/config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    JWT_SECRET_KEY         = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

    DB_NAME     = os.getenv('DB_NAME') or os.getenv('PGDATABASE')
    DB_USER     = os.getenv('DB_USER') or os.getenv('PGUSER')
    DB_PASSWORD = os.getenv('DB_PASSWORD') or os.getenv('PGPASSWORD')
    DB_HOST     = os.getenv('DB_HOST', os.getenv('PGHOST', 'localhost'))
    DB_PORT     = os.getenv('DB_PORT', os.getenv('PGPORT', '5432'))
    
    # Railway natively provides DATABASE_URL
    DATABASE_URL = os.getenv('DATABASE_URL')

    @property
    def DB_CONFIG(self):
        return {
            'dbname':   self.DB_NAME,
            'user':     self.DB_USER,
            'password': self.DB_PASSWORD,
            'host':     self.DB_HOST,
            'port':     self.DB_PORT,
        }