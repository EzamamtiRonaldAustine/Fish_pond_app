"""
pi2/analyzer.py — Water Quality Analysis Logic
==============================================
"""
from collections import deque
from . import config as CFG

class WaterQualityAnalyzer:
    def __init__(self):
        self.history = {
            "temp": deque(maxlen=CFG.HISTORY_SIZE),
            "ph":   deque(maxlen=CFG.HISTORY_SIZE),
            "n":    deque(maxlen=CFG.HISTORY_SIZE),
            "p":    deque(maxlen=CFG.HISTORY_SIZE),
        }

    def assess(self, data: dict, turbid: bool) -> dict:
        """Evaluates data and returns a status dictionary."""
        # Add to history
        if data.get("temperature"): self.history["temp"].append(data["temperature"])
        if data.get("ph"):          self.history["ph"].append(data["ph"])
        if data.get("nitrogen"):    self.history["n"].append(data["nitrogen"])
        if data.get("phosphorus"):  self.history["p"].append(data["phosphorus"])

        score = 0
        alerts = []
        
        # pH Logic
        ph = data.get("ph")
        if ph:
            if ph < CFG.THRESHOLDS["pH"]["critical_low"] or ph > CFG.THRESHOLDS["pH"]["critical_high"]:
                score += 50
                alerts.append(f"🚨 CRITICAL: pH level {ph:.1f}")
            elif ph < CFG.THRESHOLDS["pH"]["warning_low"] or ph > CFG.THRESHOLDS["pH"]["warning_high"]:
                score += 25
                alerts.append(f"⚠️ WARNING: pH level {ph:.1f}")

        # Nitrogen Logic
        n = data.get("nitrogen")
        if n and n > CFG.THRESHOLDS["nitrogen"]["critical"]:
            score += 35
            alerts.append(f"🚨 CRITICAL: Nitrogen {n:.1f}")
        
        # Overall status
        status = "GOOD"
        if score >= CFG.THRESHOLDS["quality_score"]["critical"]:
            status = "CRITICAL"
        elif score >= CFG.THRESHOLDS["quality_score"]["warning"]:
            status = "WARNING"

        return {
            "overall": status,
            "score":   score,
            "alerts":  alerts
        }

    def get_avg(self, key: str) -> float:
        h = self.history.get(key)
        return sum(h)/len(h) if h else 0.0
