"""
pi2/hardware_indicators.py — Simple Peripheral Controller
==========================================================
Manages LEDs and the Buzzers.
"""
import logging
import threading
import time
try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None
from . import config as CFG

logger = logging.getLogger("Indicators")

class IndicatorController:
    """Manages the status LEDs and PWM Buzzer."""
    
    def __init__(self):
        self._alert_silenced = False
        self._buzzer_active = False
        self._init_gpio()

    def _init_gpio(self):
        if not GPIO: return
        for led in ("LED_BLUE", "LED_YELLOW", "LED_RED", "BUZZER"):
            GPIO.setup(CFG.GPIO_PINS[led], GPIO.OUT)
        self._buzzer = GPIO.PWM(CFG.GPIO_PINS["BUZZER"], 1000)
        self._buzzer.start(0)

    def set_status(self, status: str):
        """Drives LEDs based on status."""
        self._reset_indicators()
        
        if status == "GOOD":
            self._set_led("LED_BLUE", 1)
        elif status == "WARNING":
            self._set_led("LED_YELLOW", 1)
            if not self._alert_silenced: self._beep()
        elif status == "CRITICAL":
            self._set_led("LED_RED", 1)
            if not self._alert_silenced: self._beep(continuous=True)

    def silence(self):
        self._alert_silenced = True
        if self._buzzer: self._buzzer.ChangeDutyCycle(0)

    def _reset_indicators(self):
        if not GPIO: return
        for led in ("LED_BLUE", "LED_YELLOW", "LED_RED"):
            GPIO.output(CFG.GPIO_PINS[led], 0)
        self._buzzer.ChangeDutyCycle(0)

    def _set_led(self, name: str, state: int):
        if GPIO: GPIO.output(CFG.GPIO_PINS[name], state)

    def _beep(self, continuous=False):
        if not self._buzzer: return
        def _do():
            self._buzzer_active = True
            count = 5 if not continuous else 100
            for _ in range(count):
                if self._alert_silenced: break
                self._buzzer.ChangeDutyCycle(50)
                time.sleep(0.5)
                self._buzzer.ChangeDutyCycle(0)
                time.sleep(0.5)
            self._buzzer_active = False
        threading.Thread(target=_do, daemon=True).start()
