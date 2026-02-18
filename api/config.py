# api/config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    JWT_SECRET_KEY         = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

    DB_NAME     = os.getenv('DB_NAME')
    DB_USER     = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST     = os.getenv('DB_HOST', 'localhost')
    DB_PORT     = os.getenv('DB_PORT', '5432')

    @property
    def DB_CONFIG(self):
        return {
            'dbname':   self.DB_NAME,
            'user':     self.DB_USER,
            'password': self.DB_PASSWORD,
            'host':     self.DB_HOST,
            'port':     self.DB_PORT,
        }