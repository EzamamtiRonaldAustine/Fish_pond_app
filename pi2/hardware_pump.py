"""
pi2/hardware_pump.py — Water Pump Relay Controller
==================================================
Handles pump timing and modes.
"""
import logging
import threading
import time
try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None
from . import config as CFG

logger = logging.getLogger("PumpController")

class PumpController:
    def __init__(self):
        self._running = False
        self._start_time = 0
        self._mode = "OFF"
        self._pin = CFG.GPIO_PINS["PUMP"]
        if GPIO:
            GPIO.setup(self._pin, GPIO.OUT, initial=GPIO.HIGH) # High = Relay Off
            logger.info("✅ Pump GPIO initialized — Pump held OFF")

    def start(self, mode="NORMAL"):
        if self._running: return
        self._mode = mode
        self._running = True
        self._start_time = time.time()
        if GPIO: GPIO.output(self._pin, GPIO.LOW) # Low = Relay On
        logger.info(f"Pump started in {mode} mode")

    def stop(self):
        self._running = False
        self._mode = "OFF"
        if GPIO: GPIO.output(self._pin, GPIO.HIGH)
        logger.info("Pump stopped")

    def tick(self):
        """Automatic timed stop."""
        if not self._running: return
        limit = CFG.PUMP_DURATIONS.get(self._mode, 180)
        if time.time() - self._start_time >= limit:
            logger.info("Pump cycle complete")
            self.stop()

    @property
    def is_running(self): return self._running
    
    @property
    def current_mode(self): return self._mode
