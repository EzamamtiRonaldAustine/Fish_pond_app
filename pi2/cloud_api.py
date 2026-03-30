"""
pi2/cloud_api.py — Cloud Telemetry Client
=========================================
Handles Railway and ThingSpeak updates.
"""
import logging
import requests
from . import config as CFG

logger = logging.getLogger("CloudAPI")

class CloudClient:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {"X-Device-Key": CFG.DEVICE_API_KEY}

    def post_data(self, data: dict, status: str, score: int, is_turbid: bool, alerts: list):
        try:
            payload = {
                "device_id": CFG.DEVICE_DB_ID,
                "temperature": data.get("temperature"),
                "ph": data.get("ph"),
                "ec": data.get("ec"),
                "nitrogen": data.get("nitrogen"),
                "phosphorus": data.get("phosphorus"),
                "turbidity": (1 if is_turbid else 0) if is_turbid is not None else None,
                "quality_status": status,
                "quality_score": score,
                "alerts": alerts
            }
            url = f"{CFG.API_BASE_URL}/sensors/readings"
            r = self.session.post(url, json=payload, headers=self.headers, timeout=10)
            logger.info(f"API Update: HTTP {r.status_code}")
        except Exception as e:
            logger.error(f"Railway Post failed: {e}")

    def update_thingspeak(self, data: dict):
        try:
            params = {"api_key": CFG.THINGSPEAK_API_KEY, "field1": data.get("temperature")}
            requests.get(CFG.THINGSPEAK_URL, params=params, timeout=5)
        except Exception:
            pass
            
    def fetch_commands(self) -> list:
        try:
            url = f"{CFG.API_BASE_URL}/devices/{CFG.DEVICE_DB_ID}/commands"
            r = self.session.get(url, headers=self.headers, timeout=5)
            if r.status_code == 200:
                return r.json().get("commands", [])
        except Exception:
            pass
        return []
