# dashboard/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('DASHBOARD_SECRET_KEY', 'fish-pond-dashboard-2024')
    # For unified deployment, this defaults to the dashboard's own address
    API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:10000/api')
    DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', 10000))
