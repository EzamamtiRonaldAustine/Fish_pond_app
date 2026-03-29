"""
pi2/sensor_turbidity.py — GPIO Turbidity Sensor Driver
======================================================
"""
import logging
import RPi.GPIO as GPIO
from . import config as CFG

logger = logging.getLogger("TurbiditySensor")

class TurbiditySensor:
    def __init__(self):
        self._pin = CFG.GPIO_PINS["TURBIDITY"]
        if GPIO:
            GPIO.setup(self._pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def is_turbid(self) -> bool:
        """Returns True if water is turbid (low signal), False if clear."""
        if not GPIO:
            return False
        try:
            # Typically 0 (Low) means turbid, 1 (High) means clear for these sensors
            return GPIO.input(self._pin) == 0
        except Exception as e:
            logger.error(f"Turbidity read error: {e}")
            return False
