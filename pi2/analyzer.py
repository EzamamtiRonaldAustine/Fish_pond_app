"""
pi2/analyzer.py — Water Quality Analysis Logic
==============================================
Biologically-informed scoring system.
Each parameter is weighted by how quickly and severely it harms fish.
Final score is capped at 100. Pump triggers automatically at 80 (CRITICAL).

Score Weights (fish impact ranking):
  pH Critical      → +80  (Destroys gill tissue; kills in hours; #1 danger)
  Temperature Crit → +35  (Thermal shock; also reduces dissolved oxygen)
  EC Critical      → +20  (Osmotic stress — cells cannot regulate ions)
  Turbidity High   → +15  (Clogs gills; reduces photosynthesis & oxygen)
  Phosphorus Crit  → +10  (Algae bloom → nighttime oxygen crash)
  Phosphorus Warn  → +5   (Rising algae risk)
  Temp Warning     → +15  (Metabolic stress / reduced immunity)
  pH Monitor       → +5   (Minor drift, recoverable)
  Nitrogen         →  0   (Alert only — no pump trigger per user config)
  pH Warning       →  0   (Alert only — no pump trigger per user config)
"""
from collections import deque
from . import config as CFG


class WaterQualityAnalyzer:
    def __init__(self):
        self.history = {
            "temp": deque(maxlen=CFG.HISTORY_SIZE),
            "ph":   deque(maxlen=CFG.HISTORY_SIZE),
            "ec":   deque(maxlen=CFG.HISTORY_SIZE),
            "n":    deque(maxlen=CFG.HISTORY_SIZE),
            "p":    deque(maxlen=CFG.HISTORY_SIZE),
            "turbidity": deque(maxlen=CFG.HISTORY_SIZE),
        }

    def assess(self, data: dict, turbid: bool) -> dict:
        """
        Evaluates sensor data and returns a status dictionary.

        Returns:
            dict with keys:
              overall : 'GOOD' | 'WARNING' | 'CRITICAL'
              score   : int (0–100, capped)
              alerts  : list[str]
        """
        # ── Update rolling history ─────────────────────────────────────────
        if data.get("temperature"): self.history["temp"].append(data["temperature"])
        if data.get("ph"):          self.history["ph"].append(data["ph"])
        if data.get("ec"):          self.history["ec"].append(data["ec"])
        if data.get("nitrogen"):    self.history["n"].append(data["nitrogen"])
        if data.get("phosphorus"):  self.history["p"].append(data["phosphorus"])
        self.history["turbidity"].append(1 if turbid else 0)

        score  = 0
        alerts = []

        # ── 1. pH — Most dangerous parameter (#1 killer) ──────────────────
        # Critical pH destroys gill tissue and disrupts osmoregulation.
        # At high pH, ammonia (NH3) becomes far more toxic, compounding harm.
        ph = data.get("ph")
        if ph:
            t = CFG.THRESHOLDS["pH"]
            if ph < t["critical_low"] or ph > t["critical_high"]:
                score += 80
                alerts.append(f"🚨 CRITICAL: pH {ph:.1f} — gill damage risk, pump activated")
            elif ph < t["warning_low"] or ph > t["warning_high"]:
                # Alert only — no score per user request (pump stays off)
                alerts.append(f"⚠️ WARNING: pH {ph:.1f} — outside safe range")
            elif ph < t["monitor_low"] or ph > t["monitor_high"]:
                score += 5
                alerts.append(f"ℹ️ MONITOR: pH {ph:.1f} — slight drift, watch closely")

        # ── 2. Temperature — Second highest danger ──────────────────────────
        # Fish are cold-blooded; extremes cause thermal shock and reduce oxygen.
        temp = data.get("temperature")
        if temp is not None:
            t = CFG.THRESHOLDS["temperature"]
            if temp < t["critical_low"] or temp > t["critical_high"]:
                score += 35
                alerts.append(f"🚨 CRITICAL: Temperature {temp:.1f}°C — thermal shock risk")
            elif temp < t["warning_low"] or temp > t["warning_high"]:
                score += 15
                alerts.append(f"⚠️ WARNING: Temperature {temp:.1f}°C — fish under stress")

        # ── 3. EC (Conductivity) — Osmotic stress ──────────────────────────
        # High dissolved salts disrupt ion balance in fish cells directly.
        ec = data.get("ec")
        if ec is not None and ec > CFG.THRESHOLDS["ec"]["critical_high"]:
            score += 20
            alerts.append(f"🚨 CRITICAL: EC {ec:.0f} µS/cm — osmotic stress on fish")

        # ── 4. Turbidity — Gill clog & oxygen reduction ────────────────────
        # Sustained turbidity clogs fish gills and blocks photosynthesis, 
        # reducing dissolved oxygen production.
        turbidity_ratio = (
            sum(self.history["turbidity"]) / len(self.history["turbidity"])
            if self.history["turbidity"] else 0
        )
        if turbidity_ratio > CFG.THRESHOLDS["turbidity"]["warning_ratio"]:
            score += 15
            alerts.append("⚠️ HIGH TURBIDITY — gill clog risk, reduced oxygen production")

        # ── 5. Phosphorus — Algae bloom / nighttime O₂ crash ──────────────
        # Excess phosphorus feeds algae blooms. At night, algae consume O₂
        # and fish can suffocate. Indirectly lethal but slower-acting.
        phos = data.get("phosphorus")
        if phos is not None:
            t = CFG.THRESHOLDS["phosphorus"]
            if phos > t["critical"]:
                score += 10
                alerts.append(f"🚨 CRITICAL: Phosphorus {phos:.1f} mg/L — algae bloom risk")
            elif phos > t["warning"]:
                score += 5
                alerts.append(f"⚠️ WARNING: Phosphorus {phos:.1f} mg/L — elevated, monitor algae")

        # ── 6. Nitrogen — Alert only (no pump trigger per user config) ─────
        # Nitrogen compounds (ammonia/nitrate) are toxic over time but
        # the user has opted for alert-only monitoring without pump activation.
        n = data.get("nitrogen")
        if n is not None:
            t = CFG.THRESHOLDS["nitrogen"]
            if n > t["critical"]:
                alerts.append(f"🚨 CRITICAL: Nitrogen {n:.1f} mg/L — high ammonia risk (alert only)")
            elif n > t["warning"]:
                alerts.append(f"⚠️ WARNING: Nitrogen {n:.1f} mg/L — elevated, reduce feeding")
            elif n > t["monitor"]:
                alerts.append(f"ℹ️ MONITOR: Nitrogen {n:.1f} mg/L — slightly elevated")

        # ── Final: Cap score at 100, determine overall status ──────────────
        score = min(score, 100)

        status = "GOOD"
        if score >= CFG.THRESHOLDS["quality_score"]["critical"]:
            status = "CRITICAL"
        elif score >= CFG.THRESHOLDS["quality_score"]["warning"]:
            status = "WARNING"

        return {
            "overall": status,
            "score":   score,
            "alerts":  alerts,
        }

    def get_avg(self, key: str) -> float:
        """Return rolling average for a history key."""
        h = self.history.get(key)
        return sum(h) / len(h) if h else 0.0
