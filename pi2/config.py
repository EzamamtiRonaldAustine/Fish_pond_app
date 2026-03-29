"""
pi2/config.py — Modular Configuration for AquaGuardian
========================================================
Centralized constants, thresholds, and GPIO mappings.
Refactored to eliminate magic numbers from logic files.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Path handling
BASE_DIR = Path(__file__).parent
_ENV_FILE = BASE_DIR / ".env"
if not _ENV_FILE.exists():
    _ENV_FILE = BASE_DIR.parent / "pi/.env" # Fallback to original .env if not copied

load_dotenv(_ENV_FILE)

# ── API & Identity ────────────────────────────────────────────────────────
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://fish-pond-api.up.railway.app/api")
DEVICE_DB_ID: int = int(os.getenv("DEVICE_DB_ID", "1"))
DEVICE_API_KEY: str = os.getenv("DEVICE_API_KEY", "fab17ba24a660177b4cf4c6feb5a10e5ed23bd2f3fb0a8f7")

# ── ThingSpeak ───────────────────────────────────────────────────────────
THINGSPEAK_API_KEY:  str = os.getenv("THINGSPEAK_API_KEY", "O0YOQQGDSJGFZH8P")
THINGSPEAK_URL:      str = "https://api.thingspeak.com/update"
THINGSPEAK_INTERVAL: int = int(os.getenv("THINGSPEAK_INTERVAL", "60"))

# ── Timing (Seconds) ───────────────────────────────────────────────────────
SENSOR_READ_INTERVAL:   int = int(os.getenv("SENSOR_READ_INTERVAL",   "15"))
LCD_REFRESH_INTERVAL:   int = int(os.getenv("LCD_REFRESH_INTERVAL",    "5"))
API_SEND_INTERVAL:      int = int(os.getenv("API_SEND_INTERVAL",       "60"))
COMMAND_POLL_INTERVAL:  int = int(os.getenv("COMMAND_POLL_INTERVAL",   "10"))
HEARTBEAT_INTERVAL:     int = int(os.getenv("HEARTBEAT_INTERVAL",      "15"))
WATCHDOG_INTERVAL:      int = int(os.getenv("WATCHDOG_INTERVAL",       "30"))

# ── GPIO Mapping (BCM) ─────────────────────────────────────────────────────
GPIO_PINS = {
    "TURBIDITY":  int(os.getenv("GPIO_TURBIDITY",  "17")),
    "BUZZER":     int(os.getenv("GPIO_BUZZER",      "18")),
    "LED_BLUE":   int(os.getenv("GPIO_LED_BLUE",    "27")),
    "LED_YELLOW": int(os.getenv("GPIO_LED_YELLOW",  "22")),
    "LED_RED":    int(os.getenv("GPIO_LED_RED",      "5")),
    "PUMP":       int(os.getenv("GPIO_PUMP",         "16")),
}

# ── Hardware Ports ────────────────────────────────────────────────────────
RS485_PORT:     str = os.getenv("RS485_PORT",      "/dev/ttyUSB0")
RS485_SLAVE_ID: int = int(os.getenv("RS485_SLAVE_ID", "1"))
GSM_PORT:       str = os.getenv("GSM_PORT",         "/dev/serial0")
GSM_BAUDRATE:   int = int(os.getenv("GSM_BAUDRATE", "9600"))

# ── Pump Durations (Seconds) ───────────────────────────────────────────────
PUMP_DURATIONS = {
    "SHORT":  int(os.getenv("PUMP_SHORT",  "120")),
    "NORMAL": int(os.getenv("PUMP_NORMAL", "180")),
    "LONG":   int(os.getenv("PUMP_LONG",   "240")),
}

# ── Alerts & History ───────────────────────────────────────────────────────
SMS_PHONE_NUMBERS: list = os.getenv("SMS_PHONE_NUMBERS", "+256764152908,+256770701680").split(",")
SMS_COOLDOWN:      int  = int(os.getenv("SMS_COOLDOWN",      "120"))
CRITICAL_DURATION: int  = int(os.getenv("CRITICAL_DURATION", "120"))
HISTORY_SIZE:      int  = int(os.getenv("HISTORY_SIZE",      "5"))

# ── Water Quality Thresholds ────────────────────────────────────────────────
THRESHOLDS = {
    "pH": {
        "critical_low":  5.5, "warning_low":   6.0, "monitor_low":   6.5,
        "monitor_high":  8.5, "warning_high":  9.0, "critical_high": 9.5,
    },
    "temperature": {
        "critical_low": 12.0, "warning_low": 18.0, "warning_high": 30.0, "critical_high": 35.0,
    },
    "ec": {"critical_high": 2000},
    "nitrogen":   {"monitor": 100, "warning": 150, "critical": 200},
    "phosphorus": {"monitor": 100, "warning": 150, "critical": 200},
    "turbidity":  {"warning_ratio": 0.8},
    "quality_score": {"warning": 40, "critical": 80},
}

BACKUP_CSV: str = str(BASE_DIR / "pond_data_backup.csv")
