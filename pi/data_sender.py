import requests
import json
from config_1 import API_URL, DEVICE_ID

def send_data(data):
    try:
        response = requests.post(f"{API_URL}/sensors/readings", json=data)
        print(f"Status: {response.status_code}")
    except Exception as e:
        print(f"Error sending data: {e}")
