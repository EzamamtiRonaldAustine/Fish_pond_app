"""
pi/hardware_monitor.py — Smart Fish Pond Hardware Agent
========================================================
Professional, modular rewrite of Fish_pond_system.py.

Architecture
------------
The agent is divided into focused, single-responsibility classes:

  SensorReader         — reads RS485 multi-param sensor, DS18B20, turbidity GPIO
  WaterQualityAnalyzer — evaluates readings against configurable thresholds
  HardwareController   — drives GPIO: LEDs, buzzer (PWM), pump relay
  SMSNotifier          — sends AT-command SMS via GSM module
  ThingSpeakClient     — secondary cloud backup (preserves existing dashboards)
  APIClient            — primary integration: POST readings, GET/ACK commands,
                         POST heartbeat to the Flask/PostgreSQL web API
  HardwareMonitor      — orchestrator; runs multi-threaded main loop

Data Flow
---------
  Sensor → WaterQualityAnalyzer → HardwareController  (local indicators)
                                → SMSNotifier          (sustained critical alerts)
                                → APIClient            (primary DB + commands poll)
                                → ThingSpeakClient     (secondary backup)

Author : Smart Fish Pond Development Team
Version: 2.0 — integrated with Flask/PostgreSQL API
"""

# ─────────────────────────────────────────────────────────────────────────────
# Standard library
# ─────────────────────────────────────────────────────────────────────────────
import os
import csv
import glob
import json
import logging
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Third-party (Raspberry Pi specific)
# ─────────────────────────────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
except ImportError:
    # Allow module to be imported on non-Pi machines for unit-testing
    GPIO = None

try:
    import minimalmodbus
except ImportError:
    minimalmodbus = None

try:
    import serial
except ImportError:
    serial = None

try:
    from RPLCD.i2c import CharLCD
except ImportError:
    CharLCD = None

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─────────────────────────────────────────────────────────────────────────────
# Local configuration
# ─────────────────────────────────────────────────────────────────────────────
import config_1 as CFG

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
LOG_FILE = Path(__file__).parent / "hardware_monitor.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("HardwareMonitor")


# =============================================================================
# ① SENSOR READER
# =============================================================================
class SensorReader:
    """
    Reads all water quality sensors attached to the Raspberry Pi.

    Sensors supported
    -----------------
    - RS485 multi-parameter probe (Modbus RTU) — temperature, pH, EC,
      nitrogen, phosphorus, potassium
    - DS18B20 1-Wire temperature sensor
    - Turbidity digital GPIO sensor
    """

    # Modbus register map for the RS485 probe
    _RS485_REGISTERS: dict = {
        "temperature": 19,
        "ph":          13,
        "ec":           7,
        "nitrogen":     4,
        "phosphorus":   5,
        "potassium":    6,
    }

    def __init__(self):
        self._error_count: int = 0
        self._last_successful_read: float | None = None

        self.instrument = self._init_rs485()
        self.ds18b20_file = self._init_ds18b20()

    # ── Initialisation helpers ────────────────────────────────────────────

    def _init_rs485(self):
        """Open the RS485 serial port and return a minimalmodbus Instrument."""
        if minimalmodbus is None:
            logger.warning("minimalmodbus not installed — RS485 unavailable")
            return None
        try:
            inst = minimalmodbus.Instrument(
                CFG.SENSORS["RS485_PORT"],
                CFG.SENSORS["RS485_SLAVE_ID"],
            )
            inst.serial.baudrate = 9600
            inst.serial.bytesize = 8
            inst.serial.parity   = minimalmodbus.serial.PARITY_NONE
            inst.serial.stopbits = 1
            inst.serial.timeout  = 1
            logger.info("✅ RS485 sensor initialised")
            return inst
        except Exception as exc:
            logger.error(f"❌ RS485 init failed: {exc}")
            return None

    def _init_ds18b20(self) -> str | None:
        """Locate the DS18B20 1-Wire device file."""
        try:
            os.system("modprobe w1-gpio")
            os.system("modprobe w1-therm")
            folders = glob.glob("/sys/bus/w1/devices/28-*")
            if not folders:
                logger.warning("DS18B20 sensor not found")
                return None
            dev = folders[0] + "/w1_slave"
            logger.info(f"✅ DS18B20 initialised: {dev}")
            return dev
        except Exception as exc:
            logger.error(f"❌ DS18B20 init failed: {exc}")
            return None

    # ── Public read API ───────────────────────────────────────────────────

    def read_rs485(self) -> dict:
        """
        Read all parameters from the RS485 probe.

        Returns a dict of parameter → value (or None on failure).
        Reinitialises the instrument automatically after 5 consecutive errors.
        """
        if self.instrument is None:
            self._error_count += 1
            return {}

        try:
            data: dict = {}
            # Temperature
            raw_temp = self._read_register(self._RS485_REGISTERS["temperature"])
            data["temperature"] = raw_temp

            # pH with temperature compensation
            raw_ph = self._read_register(self._RS485_REGISTERS["ph"])
            data["ph_raw"] = raw_ph
            if raw_ph is not None and raw_ph > 0.5:
                data["ph"] = self._calc_ph(raw_ph, raw_temp or 25.0)
            else:
                data["ph"] = None

            # Remaining parameters
            for param in ("ec", "nitrogen", "phosphorus", "potassium"):
                data[param] = self._read_register(self._RS485_REGISTERS[param])

            self._error_count = 0
            self._last_successful_read = time.time()
            return data

        except Exception as exc:
            self._error_count += 1
            logger.error(f"RS485 read error #{self._error_count}: {exc}")
            if self._error_count >= 5:
                logger.warning("Re-initialising RS485 instrument after 5 errors")
                self.instrument = self._init_rs485()
                self._error_count = 0
            return {}

    def read_ds18b20(self) -> float | None:
        """Read temperature from DS18B20 1-Wire sensor."""
        if not self.ds18b20_file:
            return None
        try:
            with open(self.ds18b20_file, "r") as fh:
                lines = fh.readlines()
            if lines and lines[0].strip().endswith("YES") and "t=" in lines[1]:
                temp_c = float(lines[1].split("t=")[1]) / 1000.0
                if -10 < temp_c < 60:
                    return temp_c
        except Exception as exc:
            logger.debug(f"DS18B20 read error: {exc}")
        return None

    def read_turbidity(self) -> bool | None:
        """Return True if water is turbid (digital high), False if clear."""
        if GPIO is None:
            return None
        try:
            return GPIO.input(CFG.GPIO_PINS["TURBIDITY"]) == 0
        except Exception:
            return None

    def combined_temperature(self, rs485_temp: float | None, ds18b20_temp: float | None) -> float | None:
        """Weighted average temperature from both sensors (RS485=60%, DS18B20=40%)."""
        if rs485_temp is not None and ds18b20_temp is not None:
            return 0.6 * rs485_temp + 0.4 * ds18b20_temp
        return rs485_temp if rs485_temp is not None else ds18b20_temp

    # ── Private helpers ───────────────────────────────────────────────────

    def _read_register(self, register: int, retries: int = 2) -> float | None:
        for attempt in range(retries):
            try:
                return self.instrument.read_register(register, 1, functioncode=3)
            except Exception as exc:
                logger.debug(f"Register {register} attempt {attempt + 1}: {exc}")
                if attempt < retries - 1:
                    time.sleep(0.1)
        return None

    @staticmethod
    def _calc_ph(raw_value: float, temperature: float) -> float:
        """Convert raw register value to calibrated, temperature-compensated pH."""
        ph = raw_value / 3.13
        compensated = ph - (temperature - 25) * 0.01
        return round(compensated, 2)


# =============================================================================
# ② WATER QUALITY ANALYZER
# =============================================================================
class WaterQualityAnalyzer:
    """
    Evaluates sensor readings against aquaculture-specific thresholds and
    produces a structured quality assessment: overall status, risk score,
    alert messages, and trend analysis.

    Thresholds are loaded from config.py and can be overridden per-deployment
    via environment variables.
    """

    def __init__(self):
        self.T = CFG.THRESHOLDS

        # Rolling history windows (deque automatically discards oldest)
        n = CFG.HISTORY_SIZE
        self.history: dict[str, deque] = {
            "temp":       deque(maxlen=n),
            "ph":         deque(maxlen=n),
            "ec":         deque(maxlen=n),
            "nitrogen":   deque(maxlen=n),
            "phosphorus": deque(maxlen=n),
            "turbidity":  deque(maxlen=n),
        }

    # ── Public interface ──────────────────────────────────────────────────

    def update_history(self, readings: dict, turbidity: bool | None) -> None:
        """Append latest readings to rolling history windows."""
        for key, hist_key in (
            ("temperature", "temp"),
            ("ph",          "ph"),
            ("ec",          "ec"),
            ("nitrogen",    "nitrogen"),
            ("phosphorus",  "phosphorus"),
        ):
            val = readings.get(key)
            if val is not None:
                self.history[hist_key].append(float(val))
        if turbidity is not None:
            self.history["turbidity"].append(1 if turbidity else 0)

    def assess(self, readings: dict, turbidity: bool | None) -> dict:
        """
        Assess water quality from the latest readings.

        Returns
        -------
        dict with keys:
          overall       : 'GOOD' | 'WARNING' | 'CRITICAL'
          score         : int  (0 – 150 cumulative risk score)
          alerts        : list[str]
          recommendations : set[str]
          trends        : dict[str, str]  ('INCREASING' | 'DECREASING' | 'STABLE')
        """
        self.update_history(readings, turbidity)

        status = {
            "overall": "GOOD",
            "score": 0,
            "alerts": [],
            "recommendations": set(),
            "trends": {},
        }

        avg = {k: self._avg(self.history[k]) for k in self.history}
        turbidity_ratio = (
            sum(self.history["turbidity"]) / len(self.history["turbidity"])
            if self.history["turbidity"] else 0
        )

        for param, hist_key in (("temperature", "temp"), ("ph", "ph"),
                                 ("nitrogen", "nitrogen"), ("phosphorus", "phosphorus")):
            status["trends"][param] = self._trend(self.history[hist_key])

        if not any(avg[k] is not None for k in ("temp", "ph", "ec", "nitrogen", "phosphorus")):
            status["alerts"].append("⚠️ No valid sensor data available")
            status["score"] += 50
            status["overall"] = "WARNING"
            return status

        # pH — most critical parameter
        self._check_ph(avg["ph"], status)
        # Temperature
        self._check_temperature(avg["temp"], status)
        # EC / salinity
        if avg["ec"] is not None and avg["ec"] > self.T["ec"]["critical_high"]:
            status["score"] += 30
            status["alerts"].append(f"⚠️ EC {avg['ec']:.0f} µS/cm is high")
            status["recommendations"].add("Consider diluting with fresh water")
        # Turbidity
        if turbidity_ratio > self.T["turbidity"]["warning_ratio"]:
            status["score"] += 20
            status["alerts"].append("⚠️ Water is consistently turbid")
            status["recommendations"].add("Check filter and consider water change")
        # Nutrients
        self._check_nutrient("nitrogen",   avg["nitrogen"],   status)
        self._check_nutrient("phosphorus", avg["phosphorus"], status)

        # Final overall determination
        if status["score"] >= self.T["quality_score"]["critical"]:
            status["overall"] = "CRITICAL"
        elif status["score"] >= self.T["quality_score"]["warning"]:
            status["overall"] = "WARNING"

        return status

    def get_avg(self, key: str) -> float | None:
        """Return current rolling average for a history key."""
        return self._avg(self.history.get(key, deque()))

    # ── Private helpers ───────────────────────────────────────────────────

    def _check_ph(self, avg_ph: float | None, status: dict) -> None:
        t = self.T["pH"]
        if avg_ph is None:
            status["alerts"].append("⚠️ pH sensor not in water or faulty")
            status["score"] += 30
            return
        if avg_ph < t["critical_low"]:
            status["score"] += 50
            status["alerts"].append(f"🚨 CRITICAL: pH {avg_ph:.1f} dangerously acidic")
            status["recommendations"].add("URGENT: Add agricultural lime (CaCO₃) immediately")
        elif avg_ph < t["warning_low"]:
            status["score"] += 25
            status["alerts"].append(f"⚠️ WARNING: pH {avg_ph:.1f} is acidic")
            status["recommendations"].add("Consider adding agricultural lime gradually")
        elif avg_ph < t["monitor_low"]:
            status["score"] += 10
            status["alerts"].append(f"ℹ️ pH {avg_ph:.1f} is slightly low but acceptable")
        elif avg_ph > t["critical_high"]:
            status["score"] += 50
            status["alerts"].append(f"🚨 CRITICAL: pH {avg_ph:.1f} dangerously alkaline")
            status["recommendations"].add("URGENT: Perform large water change")
        elif avg_ph > t["warning_high"]:
            status["score"] += 25
            status["alerts"].append(f"⚠️ WARNING: pH {avg_ph:.1f} is too alkaline")
            status["recommendations"].add("Perform partial water change")
        elif avg_ph > t["monitor_high"]:
            status["score"] += 10
            status["alerts"].append(f"ℹ️ pH {avg_ph:.1f} is slightly high but acceptable")

    def _check_temperature(self, avg_temp: float | None, status: dict) -> None:
        if avg_temp is None:
            return
        t = self.T["temperature"]
        if avg_temp < t["critical_low"]:
            status["score"] += 40
            status["alerts"].append(f"🚨 CRITICAL: Temperature {avg_temp:.1f}°C too cold")
            status["recommendations"].add("Add pond heater immediately")
        elif avg_temp < t["warning_low"]:
            status["score"] += 15
            status["alerts"].append(f"⚠️ Temperature {avg_temp:.1f}°C is cool")
        elif avg_temp > t["critical_high"]:
            status["score"] += 40
            status["alerts"].append(f"🚨 CRITICAL: Temperature {avg_temp:.1f}°C too hot")
            status["recommendations"].add("Add shade and emergency aeration")
        elif avg_temp > t["warning_high"]:
            status["score"] += 15
            status["alerts"].append(f"⚠️ Temperature {avg_temp:.1f}°C is warm")
            status["recommendations"].add("Monitor closely and increase aeration")

    def _check_nutrient(self, name: str, avg_val: float | None, status: dict) -> None:
        if avg_val is None:
            return
        t = self.T[name]
        if avg_val > t["critical"]:
            status["score"] += 35
            status["alerts"].append(
                f"🚨 CRITICAL: {name.capitalize()} extremely high: {avg_val:.1f} mg/kg"
            )
            status["recommendations"].add(
                f"URGENT: Stop feeding and perform large water change"
            )
        elif avg_val > t["warning"]:
            status["score"] += 20
            status["alerts"].append(
                f"⚠️ WARNING: {name.capitalize()} high: {avg_val:.1f} mg/kg"
            )
            status["recommendations"].add("Reduce feeding and increase water changes")
        elif avg_val > t["monitor"]:
            status["score"] += 5
            status["alerts"].append(
                f"ℹ️ {name.capitalize()} elevated: {avg_val:.1f} mg/kg (monitor)"
            )

    @staticmethod
    def _avg(history: deque) -> float | None:
        if not history:
            return None
        return sum(history) / len(history)

    @staticmethod
    def _trend(history: deque) -> str:
        if len(history) < 3:
            return "STABLE"
        mid = len(history) // 2
        lst = list(history)
        first = sum(lst[:mid]) / mid
        second = sum(lst[mid:]) / (len(history) - mid)
        diff = second - first
        threshold = max(0.1 * abs(first), 0.2)
        if diff > threshold:
            return "INCREASING"
        if diff < -threshold:
            return "DECREASING"
        return "STABLE"


# =============================================================================
# ③ HARDWARE CONTROLLER
# =============================================================================
class HardwareController:
    """
    Controls GPIO-attached hardware: status LEDs, PWM buzzer, and pump relay.

    Pump control is mode-based (SHORT / NORMAL / LONG), with duration limits
    from config so the pump never runs indefinitely if a thread crashes.
    """

    def __init__(self):
        self._pump_running = False
        self._pump_mode = "OFF"
        self._pump_start: float = 0.0
        self._lock = threading.Lock()

        self._alert_silenced = False
        self._last_quality_status = "GOOD"

        self._buzzer: object = None  # PWM object
        self.lcd = None

        self._init_gpio()
        self.lcd = self._init_lcd()

    # ── Initialisation ────────────────────────────────────────────────────

    def _init_gpio(self) -> None:
        if GPIO is None:
            logger.warning("RPi.GPIO not available — GPIO control simulated")
            return
        GPIO.setmode(GPIO.BCM)
        pins = CFG.GPIO_PINS
        GPIO.setup(pins["TURBIDITY"],  GPIO.IN, pull_up_down=GPIO.PUD_UP)
        for led in ("LED_BLUE", "LED_YELLOW", "LED_RED", "BUZZER", "PUMP"):
            GPIO.setup(pins[led], GPIO.OUT)
        self._buzzer = GPIO.PWM(pins["BUZZER"], 1000)
        self._buzzer.start(0)
        self._set_leds(0, 0, 0)
        GPIO.output(pins["PUMP"], GPIO.HIGH)   # Relay off by default
        logger.info("✅ GPIO initialised — Pump held OFF")

    def _init_lcd(self):
        if CharLCD is None:
            return None
        for attempt in range(3):
            try:
                lcd = CharLCD("PCF8574", 0x27)
                lcd.clear()
                lcd.write_string("Initialising...")
                logger.info("✅ LCD initialised")
                return lcd
            except Exception as exc:
                logger.error(f"LCD init attempt {attempt + 1}: {exc}")
                time.sleep(2)
        logger.warning("LCD unavailable — continuing without display")
        return None

    # ── Status updates ────────────────────────────────────────────────────

    def apply_status(self, quality_status: str, quality_status_full: dict) -> None:
        """Drive LEDs + buzzer from the quality assessment result."""
        self._set_leds(0, 0, 0)
        if self._buzzer:
            try:
                self._buzzer.ChangeDutyCycle(0)
            except Exception:
                pass

        if quality_status != self._last_quality_status:
            self._alert_silenced = False
            self._last_quality_status = quality_status

        self._led_status_str = quality_status

        if quality_status == "GOOD":
            self._set_leds(1, 0, 0)   # Blue LED = GOOD
        elif quality_status == "WARNING":
            self._set_leds(0, 1, 0)   # Yellow LED = WARNING
            if not self._alert_silenced:
                self._beep(0.2, 0.4)
        elif quality_status == "CRITICAL":
            self._set_leds(0, 0, 1)   # Red LED = CRITICAL
            if not self._alert_silenced:
                self._beep(1.0, 1.2)

    def _beep(self, on_delay: float, off_delay: float) -> None:
        if self._buzzer is None:
            return
        def _do():
            try:
                self._buzzer_active = True
                time.sleep(on_delay)
                self._buzzer.ChangeDutyCycle(50)
                time.sleep(off_delay - on_delay)
                self._buzzer.ChangeDutyCycle(0)
                self._buzzer_active = False
            except Exception:
                self._buzzer_active = False
        threading.Thread(target=_do, daemon=True).start()

    # ── Pump control ──────────────────────────────────────────────────────

    def start_pump(self, mode: str = "NORMAL") -> bool:
        """Start pump if not already running. Returns True on success."""
        with self._lock:
            if self._pump_running:
                logger.info(f"Pump already running in {self._pump_mode} mode")
                return False
            self._pump_mode    = mode
            self._pump_running = True
            self._pump_start   = time.time()
        if GPIO is not None:
            try:
                GPIO.output(CFG.GPIO_PINS["PUMP"], GPIO.LOW)   # LOW = relay on
            except RuntimeError as exc:
                logger.debug(f"GPIO error in start_pump: {exc}")
        logger.info(f"▶️  Pump started in {mode} mode")
        return True

    def stop_pump(self) -> None:
        """Stop the pump immediately (forces high state on relay)."""
        with self._lock:
            self._pump_running = False
            self._pump_mode    = "OFF"
        if GPIO is not None:
            try:
                GPIO.output(CFG.GPIO_PINS["PUMP"], GPIO.HIGH)  # Force HIGH = relay off
            except RuntimeError as exc:
                logger.debug(f"GPIO error in stop_pump: {exc}")
        logger.info("⏹️  Pump stopped")

    def tick_pump(self) -> None:
        """Call periodically; stops pump when its timed cycle expires."""
        with self._lock:
            if not self._pump_running:
                return
            mode = self._pump_mode
            start = self._pump_start
        duration = CFG.PUMP_DURATIONS.get(mode, CFG.PUMP_DURATIONS["NORMAL"])
        if time.time() - start >= duration:
            logger.info(f"⏹️  {mode} pump cycle complete")
            self.stop_pump()

    def determine_pump_mode(self, analyzer: "WaterQualityAnalyzer") -> str:
        avg_temp = analyzer.get_avg("temp")
        avg_ph   = analyzer.get_avg("ph")
        turb_ratio = (
            sum(analyzer.history["turbidity"]) / len(analyzer.history["turbidity"])
            if analyzer.history["turbidity"] else 0
        )
        if avg_temp is not None and (avg_temp < 15 or avg_temp > 32):
            return "LONG"
        if avg_ph is not None and (avg_ph < 6.0 or avg_ph > 9.0):
            return "SHORT"
        if turb_ratio > 0.7:
            return "NORMAL"
        return "NORMAL"

    # ── State getters (for heartbeat) ─────────────────────────────────────

    @property
    def pump_running(self) -> bool:
        return self._pump_running

    @property
    def pump_mode(self) -> str:
        return self._pump_mode

    @property
    def led_status(self) -> str:
        """Return the logical status currently shown on the LEDs."""
        return getattr(self, "_led_status_str", "GOOD")

    @property
    def buzzer_active(self) -> bool:
        """Return True if the buzzer is currently beeping/active."""
        return getattr(self, "_buzzer_active", False)

    def _set_leds(self, blue: int, yellow: int, red: int) -> None:
        if GPIO is None:
            return
        pins = CFG.GPIO_PINS
        try:
            GPIO.output(pins["LED_BLUE"],   blue)
            GPIO.output(pins["LED_YELLOW"], yellow)
            GPIO.output(pins["LED_RED"],    red)
        except Exception as exc:
            logger.debug(f"LED error: {exc}")

    # ── LCD update (simplified — main logic kept from original) ───────────

    def update_lcd(self, line1: str, line2: str) -> None:
        if self.lcd is None:
            return
        try:
            line1 = line1[:16].ljust(16)
            line2 = line2[:16].ljust(16)
            self.lcd.clear()
            time.sleep(0.01)
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(line1)
            time.sleep(0.01)
            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string(line2)
        except Exception as exc:
            logger.error(f"LCD write error: {exc}")

    # ── Cleanup ───────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        self.stop_pump()
        if GPIO is not None:
            # Explicitly hold pump relay OFF (HIGH) before releasing pins
            # This helps prevent the relay from triggering as an accidental input
            try:
                GPIO.output(CFG.GPIO_PINS["PUMP"], GPIO.HIGH)
                time.sleep(0.1)
            except Exception:
                pass

        # ── LCD shutdown ─────────────────────────────────────────────────────
        if self.lcd is not None:
            try:
                # Show a brief "offline" message, then blank display & backlight
                self.lcd.clear()
                self.lcd.cursor_pos = (0, 0)
                self.lcd.write_string("  System Offline")
                self.lcd.cursor_pos = (1, 0)
                self.lcd.write_string("   Shutting down")
                time.sleep(1.5)
                self.lcd.clear()
                self.lcd.backlight_enabled = False
            except Exception as exc:
                logger.debug(f"LCD cleanup error: {exc}")

        if self._buzzer:
            try:
                self._buzzer.stop()
            except Exception:
                pass
        if GPIO is not None:
            GPIO.cleanup()
        logger.info("GPIO and LCD cleaned up")


# =============================================================================
# ④ SMS NOTIFIER
# =============================================================================
class SMSNotifier:
    """Sends alert SMS via a GSM module using AT commands."""

    def __init__(self):
        self._gsm = self._init_gsm()
        self._lock = threading.Lock()
        self._last_sent: float = 0.0

    def _init_gsm(self):
        if serial is None:
            logger.warning("pyserial not installed — GSM unavailable")
            return None
        try:
            ser = serial.Serial(
                port     = CFG.SENSORS["GSM_PORT"],
                baudrate = CFG.SENSORS["GSM_BAUDRATE"],
                timeout  = 5,
            )
            for cmd in ("AT", "ATE0", "AT+CMGF=1"):
                self._send_at(ser, cmd)
            logger.info("✅ GSM module initialised")
            return ser
        except Exception as exc:
            logger.error(f"❌ GSM init failed: {exc}")
            return None

    def send_alert(self, assessment: dict) -> bool:
        """Send SMS alert if cooldown has elapsed."""
        if not self._gsm:
            return False
        now = time.time()
        if now - self._last_sent < CFG.SMS_COOLDOWN:
            return False

        message = (
            f"🚨 POND ALERT ({assessment['overall']})\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            "Issues:\n" + "\n".join(assessment["alerts"][:3])
        )
        if assessment["recommendations"]:
            message += "\n\nActions:\n" + "\n".join(list(assessment["recommendations"])[:2])

        success = False
        with self._lock:
            for phone in CFG.SMS_PHONE_NUMBERS:
                try:
                    self._gsm.write(f'AT+CMGS="{phone.strip()}"\r\n'.encode())
                    time.sleep(1)
                    self._gsm.write(message.encode())
                    time.sleep(0.5)
                    self._gsm.write(b"\x1A")   # CTRL+Z to send
                    time.sleep(5)
                    resp = self._gsm.read_all().decode(errors="ignore")
                    if "+CMGS:" in resp:
                        logger.info(f"✅ SMS sent to {phone}")
                        success = True
                    else:
                        logger.error(f"❌ SMS failed to {phone}: {resp.strip()[:80]}")
                except Exception as exc:
                    logger.error(f"SMS error for {phone}: {exc}")
        if success:
            self._last_sent = now
        return success

    @staticmethod
    def _send_at(ser, command: str, delay: float = 1.0) -> str:
        try:
            ser.write((command + "\r\n").encode())
            time.sleep(delay)
            return ser.read_all().decode(errors="ignore").strip()
        except Exception as exc:
            logger.error(f"AT command '{command}' error: {exc}")
            return ""


# =============================================================================
# ⑤ THINGSPEAK CLIENT  (secondary cloud backup)
# =============================================================================
class ThingSpeakClient:
    """
    Posts sensor data to ThingSpeak as a secondary cloud backup.

    ThingSpeak Field Mapping
    ------------------------
    field1 — Temperature (°C)
    field2 — pH
    field3 — Electrical Conductivity (µS/cm)
    field4 — Nitrogen (mg/kg)
    field5 — Phosphorus (mg/kg)
    field6 — Turbidity (0 = clear, 1 = turbid)
    field7 — Quality score (0–150)
    field8 — Quality status code (0 = GOOD, 1 = WARNING, 2 = CRITICAL)
    """

    _STATUS_CODE = {"GOOD": 0, "WARNING": 1, "CRITICAL": 2}

    def __init__(self):
        self._last_sent: float = 0.0
        self._ok: bool = True
        self._ensure_backup_file()

    def send(self, readings: dict, assessment: dict, turbidity: bool | None) -> bool:
        """Build payload and POST to ThingSpeak. Falls back to CSV on failure."""
        now = time.time()
        if now - self._last_sent < CFG.THINGSPEAK_INTERVAL:
            return True   # Rate-limit not yet elapsed

        payload = {"api_key": CFG.THINGSPEAK_API_KEY}
        if readings.get("temperature") is not None:
            payload["field1"] = readings["temperature"]
        if readings.get("ph") is not None:
            payload["field2"] = readings["ph"]
        if readings.get("ec") is not None:
            payload["field3"] = readings["ec"]
        if readings.get("nitrogen") is not None:
            payload["field4"] = readings["nitrogen"]
        if readings.get("phosphorus") is not None:
            payload["field5"] = readings["phosphorus"]
        if turbidity is not None:
            payload["field6"] = 1 if turbidity else 0
        if assessment.get("score") is not None:
            payload["field7"] = assessment["score"]
        payload["field8"] = self._STATUS_CODE.get(
            str(assessment.get("overall", "GOOD")).upper(), -1
        )

        try:
            resp = requests.get(CFG.THINGSPEAK_URL, params=payload, timeout=10)
            result = resp.text.strip()
            if resp.status_code == 200 and result.isdigit():
                entry_id = int(result)
                if entry_id > 0:
                    self._last_sent = now
                    self._ok = True
                    logger.info(f"☁️  ThingSpeak entry {result} saved")
                    return True
                else:
                    logger.warning(f"ThingSpeak error: Key rejection or rate limit (Response: {result})")
            else:
                logger.warning(f"ThingSpeak unexpected response: {result} (HTTP {resp.status_code})")
        except Exception as exc:
            logger.error(f"ThingSpeak POST failed: {exc}")

        self._ok = False
        self._save_backup(readings, assessment, turbidity)
        return False

    @property
    def is_ok(self) -> bool:
        return self._ok

    def _ensure_backup_file(self) -> None:
        if not os.path.exists(CFG.BACKUP_CSV):
            try:
                with open(CFG.BACKUP_CSV, "w", newline="") as fh:
                    csv.writer(fh).writerow([
                        "timestamp", "temperature", "ph", "ec",
                        "nitrogen", "phosphorus", "turbidity",
                        "quality_score", "quality_status",
                    ])
            except Exception as exc:
                logger.error(f"Could not create backup CSV: {exc}")

    def _save_backup(self, readings: dict, assessment: dict, turbidity: bool | None) -> None:
        try:
            with open(CFG.BACKUP_CSV, "a", newline="") as fh:
                csv.writer(fh).writerow([
                    datetime.now().isoformat(),
                    readings.get("temperature"),
                    readings.get("ph"),
                    readings.get("ec"),
                    readings.get("nitrogen"),
                    readings.get("phosphorus"),
                    1 if turbidity else 0,
                    assessment.get("score"),
                    assessment.get("overall"),
                ])
        except Exception as exc:
            logger.error(f"Backup CSV write failed: {exc}")


class SSLCustomAdapter(HTTPAdapter):
    """
    A custom HTTP adapter that forces a smaller SSL/TLS handshake.
    Used to bypass MTU-related 'Unexpected EOF' errors on restricted networks.
    """
    def init_poolmanager(self, *args, **kwargs):
        # Create a custom SSL context
        context = ssl.create_default_context()
        
        # Use a high-security but 'small handshake' cipher set.
        # This prevents the 'Client Hello' from exceeding the 1500-byte MTU limit
        # by avoiding massive Post-Quantum key exchange extensions.
        context.set_ciphers('ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256')
        
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)


# =============================================================================
# ⑥ API CLIENT  (primary integration with Flask/PostgreSQL web app)
# =============================================================================
class APIClient:
    """
    Handles all communication between the Raspberry Pi and the Flask API.

    Responsibilities
    ----------------
    POST /api/sensors/readings   — Push sensor data to the database
    POST /api/devices/{id}/status — Push live hardware heartbeat
    GET  /api/devices/{id}/commands  — Poll for pending web commands
    PATCH /api/devices/{id}/commands/{cid}/ack — Acknowledge + mark executed
    """

    _DEVICE_KEY_HEADER = "X-Device-Key"

    def __init__(self):
        self._device_id = CFG.DEVICE_DB_ID
        self._api_key   = CFG.DEVICE_API_KEY
        self._base      = CFG.API_BASE_URL.rstrip("/")
        self._ok        = True
        self._session   = self._build_session()

    # ── Sensor data ingest ────────────────────────────────────────────────

    def post_readings(self, readings: dict, assessment: dict, turbidity: bool | None) -> bool:
        """
        POST a complete sensor snapshot to POST /api/sensors/readings.
        The API validates and writes it to the sensor_readings table.
        """
        payload = {
            "device_id":      self._device_id,
            "temperature":    readings.get("temperature"),
            "ph":             readings.get("ph"),
            "ec":             readings.get("ec"),
            "nitrogen":       readings.get("nitrogen"),
            "phosphorus":     readings.get("phosphorus"),
            "turbidity":      (1 if turbidity else 0) if turbidity is not None else None,
            "quality_score":  assessment.get("score"),
            "quality_status": assessment.get("overall", "GOOD"),
            "alerts":         assessment.get("alerts", []),
        }
        try:
            resp = self._session.post(
                f"{self._base}/sensors/readings",
                json=payload,
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code in (200, 201):
                self._ok = True
                logger.info(f"📤 Readings posted to API (HTTP {resp.status_code})")
                return True
            else:
                logger.warning(f"API readings POST → HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as exc:
            logger.error(f"API readings POST failed: {exc}")
        self._ok = False
        return False

    # ── Live status heartbeat ─────────────────────────────────────────────

    def post_status(self, hardware: "HardwareController", assessment: dict,
                    uptime: float, network_ok: bool, thingspeak_ok: bool) -> bool:
        """Push live hardware state to POST /api/devices/{id}/status."""
        payload = {
            "pump_running":    hardware.pump_running,
            "pump_mode":       hardware.pump_mode,
            "led_status":      hardware.led_status,
            "buzzer_active":   hardware.buzzer_active,
            "quality_status":  assessment.get("overall", "GOOD"),
            "quality_score":   assessment.get("score", 0),
            "is_online":       True,
            "uptime_seconds":  int(uptime),
            "network_ok":      network_ok,
            "thingspeak_ok":   thingspeak_ok,
            "api_ok":          self._ok,
        }
        try:
            resp = self._session.post(
                f"{self._base}/devices/{self._device_id}/status",
                json=payload,
                headers=self._headers(),
                timeout=8,
            )
            if resp.status_code in (200, 201):
                return True
            logger.warning(f"Status heartbeat → HTTP {resp.status_code}")
        except Exception as exc:
            logger.debug(f"Heartbeat failed: {exc}")
        return False

    # ── Command polling ───────────────────────────────────────────────────

    def fetch_commands(self) -> list[dict]:
        """
        GET /api/devices/{id}/commands — returns list of pending commands.
        Each item: { "id": int, "command": str, "parameters": dict }
        """
        try:
            resp = self._session.get(
                f"{self._base}/devices/{self._device_id}/commands",
                headers=self._headers(),
                timeout=8,
            )
            if resp.status_code == 200:
                return resp.json().get("commands", [])
        except Exception as exc:
            logger.debug(f"Command poll failed: {exc}")
        return []

    def acknowledge_command(self, command_id: int, success: bool = True,
                            error_msg: str | None = None) -> None:
        """PATCH /api/devices/{id}/commands/{cid}/ack — close out a command."""
        payload = {
            "status":        "executed" if success else "failed",
            "error_message": error_msg,
        }
        try:
            self._session.patch(
                f"{self._base}/devices/{self._device_id}/commands/{command_id}/ack",
                json=payload,
                headers=self._headers(),
                timeout=8,
            )
        except Exception as exc:
            logger.debug(f"ACK failed for cmd {command_id}: {exc}")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {self._DEVICE_KEY_HEADER: self._api_key}

    @property
    def is_ok(self) -> bool:
        return self._ok

    @staticmethod
    def _build_session() -> requests.Session:
        """Build a requests session with automatic retry and MTU-friendly SSL."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
        )
        # Use our custom adapter for HTTPS to ensure small handshake packets
        adapter = SSLCustomAdapter(max_retries=retry)
        session.mount("http://",  HTTPAdapter(max_retries=retry))
        session.mount("https://", adapter)
        return session


# =============================================================================
# ⑦ HARDWARE MONITOR  (orchestrator)
# =============================================================================
class HardwareMonitor:
    """
    Top-level orchestrator that wires all sub-components together and manages
    the multi-threaded main loop.

    Threads
    -------
    monitor_thread    — sensor read + quality assess + GPIO → every SENSOR_READ_INTERVAL
    api_thread        — POST readings + POST heartbeat    → every API_SEND / HEARTBEAT
    command_thread    — poll + execute commands           → every COMMAND_POLL_INTERVAL
    thingspeak_thread — secondary cloud backup           → rate-limited internally
    sms_thread        — sustained-critical SMS alerts    → every SENSOR_READ_INTERVAL
    watchdog_thread   — thread health monitoring         → every WATCHDOG_INTERVAL
    """

    def __init__(self):
        self._start_time = time.time()
        self._running    = True
        self._stopping   = False

        # Sub-components
        self.sensors    = SensorReader()
        self.analyzer   = WaterQualityAnalyzer()
        self.hardware   = HardwareController()
        self.sms        = SMSNotifier()
        self.thingspeak = ThingSpeakClient()
        self.api        = APIClient()

        # Shared state (protected by _lock)
        self._lock = threading.Lock()
        self._latest_readings:   dict = {}
        self._latest_assessment: dict = {"overall": "GOOD", "score": 0, "alerts": [],
                                          "recommendations": set(), "trends": {}}
        self._latest_turbidity:  bool | None = None

        # Critical-condition tracking (for sustained SMS threshold)
        self._critical_start:  float | None = None
        self._critical_alerted: bool = False

        # Watchdog timestamps (each thread updates its slot every cycle)
        self._watchdog: dict[str, float] = {
            "monitor":    time.time(),
            "api":        time.time(),
            "command":    time.time(),
            "thingspeak": time.time(),
            "sms":        time.time(),
        }

        # Network connectivity cache
        self._network_ok = True

        logger.info("=" * 60)
        logger.info("Smart Fish Pond Hardware Agent v2.0 starting")
        logger.info(f"API target : {CFG.API_BASE_URL}")
        logger.info(f"Device ID  : {CFG.DEVICE_DB_ID}")
        logger.info("=" * 60)

    # ── Thread targets ────────────────────────────────────────────────────

    def _monitor_loop(self) -> None:
        """Read sensors, assess quality, update hardware indicators."""
        while self._running:
            try:
                rs485_data  = self.sensors.read_rs485()
                ds18b20_tmp = self.sensors.read_ds18b20()
                turbidity   = self.sensors.read_turbidity()

                # Merge temperatures
                if rs485_data:
                    rs485_data["temperature"] = self.sensors.combined_temperature(
                        rs485_data.get("temperature"), ds18b20_tmp
                    )

                assessment = self.analyzer.assess(rs485_data, turbidity)

                with self._lock:
                    self._latest_readings   = rs485_data
                    self._latest_assessment = assessment
                    self._latest_turbidity  = turbidity

                self.hardware.apply_status(assessment["overall"], assessment)
                self.hardware.tick_pump()

                # Auto-pump on CRITICAL
                if (assessment["overall"] == "CRITICAL"
                        and not self.hardware.pump_running):
                    mode = self.hardware.determine_pump_mode(self.analyzer)
                    self.hardware.start_pump(mode)

                # LCD update
                temp_avg = self.analyzer.get_avg("temp")
                ph_avg   = self.analyzer.get_avg("ph")
                line1 = f"T:{temp_avg:.1f}C pH:{ph_avg:.1f}" if temp_avg and ph_avg else assessment["overall"]
                line2 = f"Score:{assessment['score']}"
                self.hardware.update_lcd(line1, line2)

                self._watchdog["monitor"] = time.time()
                logger.info(
                    f"[Monitor] status={assessment['overall']} score={assessment['score']}"
                    f" temp={temp_avg} pH={ph_avg}"
                )

            except Exception as exc:
                logger.error(f"Monitor loop error: {exc}", exc_info=True)

            time.sleep(CFG.SENSOR_READ_INTERVAL)

    def _api_loop(self) -> None:
        """Post sensor readings and heartbeat to the Flask API."""
        last_reading_post = 0.0
        while self._running:
            try:
                self._network_ok = self._check_network()
                with self._lock:
                    readings   = dict(self._latest_readings)
                    assessment = dict(self._latest_assessment)
                    turbidity  = self._latest_turbidity

                now = time.time()
                if self._network_ok and readings:
                    # POST sensor reading (rate-limited)
                    if now - last_reading_post >= CFG.API_SEND_INTERVAL:
                        if self.api.post_readings(readings, assessment, turbidity):
                            last_reading_post = now

                # Heartbeat every cycle regardless
                uptime = now - self._start_time
                self.api.post_status(
                    self.hardware, assessment, uptime,
                    self._network_ok, self.thingspeak.is_ok,
                )

                self._watchdog["api"] = time.time()

            except Exception as exc:
                logger.error(f"API loop error: {exc}", exc_info=True)

            time.sleep(CFG.HEARTBEAT_INTERVAL)

    def _command_loop(self) -> None:
        """Poll the API for pending commands and execute them."""
        while self._running:
            try:
                commands = self.api.fetch_commands()
                for cmd in commands:
                    self._execute_command(cmd)
                self._watchdog["command"] = time.time()
            except Exception as exc:
                logger.error(f"Command loop error: {exc}", exc_info=True)
            time.sleep(CFG.COMMAND_POLL_INTERVAL)

    def _thingspeak_loop(self) -> None:
        """Push data to ThingSpeak as secondary cloud backup."""
        while self._running:
            try:
                with self._lock:
                    readings   = dict(self._latest_readings)
                    assessment = dict(self._latest_assessment)
                    turbidity  = self._latest_turbidity

                if readings:
                    self.thingspeak.send(readings, assessment, turbidity)

                self._watchdog["thingspeak"] = time.time()
            except Exception as exc:
                logger.error(f"ThingSpeak loop error: {exc}", exc_info=True)
            time.sleep(CFG.THINGSPEAK_INTERVAL)

    def _sms_loop(self) -> None:
        """Send SMS when a CRITICAL condition is sustained beyond the threshold."""
        while self._running:
            try:
                with self._lock:
                    assessment = dict(self._latest_assessment)

                if assessment.get("overall") == "CRITICAL":
                    if self._critical_start is None:
                        self._critical_start   = time.time()
                        self._critical_alerted = False
                        logger.info("⚠️  Critical sustained timer started")
                    elif (not self._critical_alerted
                          and time.time() - self._critical_start >= CFG.CRITICAL_DURATION):
                        logger.info("🚨 Sending sustained-critical SMS")
                        self.sms.send_alert(assessment)
                        self._critical_alerted = True
                else:
                    if self._critical_start is not None:
                        logger.info("✅ Critical condition recovered")
                    self._critical_start   = None
                    self._critical_alerted = False

                self._watchdog["sms"] = time.time()
            except Exception as exc:
                logger.error(f"SMS loop error: {exc}", exc_info=True)

            time.sleep(CFG.SENSOR_READ_INTERVAL)

    def _watchdog_loop(self) -> None:
        """Monitor thread health and log warnings for stuck threads."""
        max_silence = CFG.WATCHDOG_INTERVAL * 3
        while self._running:
            now = time.time()
            for name, last in self._watchdog.items():
                age = now - last
                if age > max_silence:
                    logger.warning(
                        f"⚠️  Thread '{name}' has been silent for {age:.0f}s "
                        f"(threshold {max_silence}s)"
                    )
            time.sleep(CFG.WATCHDOG_INTERVAL)

    # ── Command dispatcher ────────────────────────────────────────────────

    def _execute_command(self, cmd: dict) -> None:
        """Execute a single hardware command received from the web API."""
        cid     = cmd.get("id")
        command = cmd.get("command", "").upper()
        params  = cmd.get("parameters", {})

        logger.info(f"▶️  Executing command #{cid}: {command} params={params}")

        try:
            if command == "PUMP_ON":
                mode = params.get("mode", "NORMAL").upper()
                self.hardware.start_pump(mode)
            elif command == "PUMP_OFF":
                self.hardware.stop_pump()
            elif command in ("PUMP_SHORT", "PUMP_LONG", "PUMP_NORMAL"):
                mode = command.split("_")[1]
                self.hardware.start_pump(mode)
            elif command == "CLEAR_ALERT":
                self.hardware._alert_silenced = True
                logger.info("Alert silenced by web command")
            elif command == "SYSTEM_SHUTDOWN":
                logger.info("Shutdown command received — stopping agent")
                self.api.acknowledge_command(cid, success=True)
                self.stop()
                return
            elif command == "SYSTEM_RESTART":
                logger.info("Restart command received")
                self.api.acknowledge_command(cid, success=True)
                self.stop()
                os.execv(sys.executable, [sys.executable] + sys.argv)
                return
            else:
                logger.warning(f"Unknown command: {command}")
                self.api.acknowledge_command(cid, success=False,
                                             error_msg=f"Unknown command: {command}")
                return

            self.api.acknowledge_command(cid, success=True)

        except Exception as exc:
            logger.error(f"Command execution failed for #{cid}: {exc}")
            self.api.acknowledge_command(cid, success=False, error_msg=str(exc))

    # ── Run / stop ────────────────────────────────────────────────────────

    def run(self) -> None:
        """
        Start all background threads and block until shutdown is requested.

        Call ``stop()`` from a signal handler or another thread to exit cleanly.
        """
        threads = [
            threading.Thread(target=self._monitor_loop,    name="Monitor",    daemon=True),
            threading.Thread(target=self._api_loop,        name="API",        daemon=True),
            threading.Thread(target=self._command_loop,    name="Command",    daemon=True),
            threading.Thread(target=self._thingspeak_loop, name="ThingSpeak", daemon=True),
            threading.Thread(target=self._sms_loop,        name="SMS",        daemon=True),
            threading.Thread(target=self._watchdog_loop,   name="Watchdog",   daemon=True),
        ]
        for t in threads:
            t.start()
            logger.info(f"Thread started: {t.name}")

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received — shutting down")
        finally:
            self.stop()

    def stop(self) -> None:
        """Request graceful shutdown of all threads."""
        with self._lock:
            if self._stopping:
                return
            self._stopping = True
            
        logger.info("Stopping hardware agent...")
        self._running = False
        self.hardware.cleanup()
        logger.info("Hardware agent stopped")

    # ── Network helper ────────────────────────────────────────────────────

    @staticmethod
    def _check_network() -> bool:
        try:
            socket.setdefaulttimeout(3)
            socket.gethostbyname("8.8.8.8")
            return True
        except Exception:
            return False


# =============================================================================
# ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    import signal

    monitor = HardwareMonitor()

    def _handle_signal(signum, frame):
        logger.info(f"Signal {signum} received — initiating shutdown")
        monitor.stop()

    # Graceful shutdown on SIGTERM / SIGINT
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    monitor.run()
