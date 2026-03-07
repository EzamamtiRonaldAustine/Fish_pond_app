"""
pi/config.py — Raspberry Pi Hardware Agent Configuration
=========================================================
All settings for the Smart Fish Pond Hardware Agent.
Values are loaded from a .env file located in the same directory so no
credentials are hard-coded in source control.

Create a file called ``pi/.env`` (not committed to git) with the mandatory
variables listed under MANDATORY SETTINGS below.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from this script's directory (the pi/ folder on the Raspberry Pi)
_ENV_FILE = Path(__file__).parent / ".env"
load_dotenv(_ENV_FILE)

# ==============================================================================
# MANDATORY SETTINGS  (must be set in pi/.env)
# ==============================================================================

# Base URL of the Flask API server (no trailing slash)
# Example: http://192.168.1.100:5000/api   or   https://mypond.example.com/api
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://127.0.0.1:5000/api")

# Numeric database ID of this Raspberry Pi's device record in the `devices` table
# Obtain this after running:  POST /api/devices  or checking the admin dashboard
DEVICE_DB_ID: int = int(os.getenv("DEVICE_DB_ID", "1"))

# Pre-shared API key used to authenticate Pi ↔ API calls (no JWT needed on device)
# Set this in the API's .env as   DEVICE_API_KEY=<same value>
DEVICE_API_KEY: str = os.getenv("DEVICE_API_KEY", "CHANGE_ME_DEVICE_SECRET")

# ==============================================================================
# THINGSPEAK  (secondary cloud backup  — keeps existing dashboards working)
# ==============================================================================
THINGSPEAK_API_KEY:  str = os.getenv("THINGSPEAK_API_KEY", "O0YOQQGDSJGFZH8P")
THINGSPEAK_URL:      str = "https://api.thingspeak.com/update"
THINGSPEAK_INTERVAL: int = int(os.getenv("THINGSPEAK_INTERVAL", "60"))   # seconds

# ==============================================================================
# TIMING  (seconds)
# ==============================================================================
SENSOR_READ_INTERVAL:   int = int(os.getenv("SENSOR_READ_INTERVAL",   "15"))
LCD_REFRESH_INTERVAL:   int = int(os.getenv("LCD_REFRESH_INTERVAL",    "5"))
API_SEND_INTERVAL:      int = int(os.getenv("API_SEND_INTERVAL",       "60"))
COMMAND_POLL_INTERVAL:  int = int(os.getenv("COMMAND_POLL_INTERVAL",   "10"))
HEARTBEAT_INTERVAL:     int = int(os.getenv("HEARTBEAT_INTERVAL",      "15"))
WATCHDOG_INTERVAL:      int = int(os.getenv("WATCHDOG_INTERVAL",       "30"))

# ==============================================================================
# GPIO PIN MAP  (BCM numbering)
# ==============================================================================
GPIO_PINS: dict = {
    "TURBIDITY":  int(os.getenv("GPIO_TURBIDITY",  "17")),  # Digital input
    "BUZZER":     int(os.getenv("GPIO_BUZZER",      "18")),  # PWM output
    "LED_BLUE":   int(os.getenv("GPIO_LED_BLUE",    "27")),  # GOOD  indicator
    "LED_YELLOW": int(os.getenv("GPIO_LED_YELLOW",  "22")),  # WARNING indicator
    "LED_RED":    int(os.getenv("GPIO_LED_RED",      "5")),  # CRITICAL indicator
    "PUMP":       int(os.getenv("GPIO_PUMP",         "16")),  # Relay output
}

# ==============================================================================
# SENSOR INTERFACES
# ==============================================================================
SENSORS: dict = {
    "RS485_PORT":      os.getenv("RS485_PORT",      "/dev/ttyUSB0"),
    "RS485_SLAVE_ID":  int(os.getenv("RS485_SLAVE_ID", "1")),
    "GSM_PORT":        os.getenv("GSM_PORT",         "/dev/serial0"),
    "GSM_BAUDRATE":    int(os.getenv("GSM_BAUDRATE", "9600")),
}

# ==============================================================================
# PUMP DURATIONS  (seconds)
# ==============================================================================
PUMP_DURATIONS: dict = {
    "SHORT":  int(os.getenv("PUMP_SHORT",  "120")),   # pH emergencies
    "NORMAL": int(os.getenv("PUMP_NORMAL", "180")),   # Standard aeration
    "LONG":   int(os.getenv("PUMP_LONG",   "240")),   # Temperature emergencies
}

# ==============================================================================
# ALERTS / SMS
# ==============================================================================
SMS_PHONE_NUMBERS:  list = os.getenv(
    "SMS_PHONE_NUMBERS", "+256764152908,+256770701680"
).split(",")
SMS_COOLDOWN:       int = int(os.getenv("SMS_COOLDOWN",       "120"))
CRITICAL_DURATION:  int = int(os.getenv("CRITICAL_DURATION",  "120"))

# ==============================================================================
# HISTORY / ROLLING WINDOW
# ==============================================================================
HISTORY_SIZE: int = int(os.getenv("HISTORY_SIZE", "5"))

# ==============================================================================
# WATER QUALITY THRESHOLDS  (calibrated for aquaculture)
# ==============================================================================
THRESHOLDS: dict = {
    "pH": {
        "critical_low":  float(os.getenv("PH_CRITICAL_LOW",  "5.5")),
        "warning_low":   float(os.getenv("PH_WARNING_LOW",   "6.0")),
        "monitor_low":   float(os.getenv("PH_MONITOR_LOW",   "6.5")),
        "monitor_high":  float(os.getenv("PH_MONITOR_HIGH",  "8.5")),
        "warning_high":  float(os.getenv("PH_WARNING_HIGH",  "9.0")),
        "critical_high": float(os.getenv("PH_CRITICAL_HIGH", "9.5")),
    },
    "temperature": {
        "critical_low":  float(os.getenv("TEMP_CRITICAL_LOW",  "12.0")),
        "warning_low":   float(os.getenv("TEMP_WARNING_LOW",   "18.0")),
        "warning_high":  float(os.getenv("TEMP_WARNING_HIGH",  "30.0")),
        "critical_high": float(os.getenv("TEMP_CRITICAL_HIGH", "35.0")),
    },
    "ec": {
        "critical_high": float(os.getenv("EC_CRITICAL_HIGH", "2000")),
    },
    "nitrogen": {
        "monitor":  float(os.getenv("N_MONITOR",  "100")),
        "warning":  float(os.getenv("N_WARNING",  "150")),
        "critical": float(os.getenv("N_CRITICAL", "200")),
    },
    "phosphorus": {
        "monitor":  float(os.getenv("P_MONITOR",  "100")),
        "warning":  float(os.getenv("P_WARNING",  "150")),
        "critical": float(os.getenv("P_CRITICAL", "200")),
    },
    "turbidity": {
        "warning_ratio":  float(os.getenv("TURBIDITY_WARNING_RATIO",  "0.8")),
    },
    "quality_score": {
        "warning":  int(os.getenv("SCORE_WARNING",  "40")),
        "critical": int(os.getenv("SCORE_CRITICAL", "80")),
    },
}

# ==============================================================================
# LOCAL BACKUP  (offline CSV when API and ThingSpeak are unreachable)
# ==============================================================================
BACKUP_CSV: str = os.getenv(
    "BACKUP_CSV",
    str(Path(__file__).parent / "pond_data_backup.csv")
)
