"""
pi2/hardware_lcd.py — I2C LCD Display Controller
================================================
"""
import logging
import time
try:
    from RPLCD.i2c import CharLCD
except ImportError:
    CharLCD = None

logger = logging.getLogger("LCD")

class LCDController:
    def __init__(self):
        self.lcd = self._init_lcd()

    def _init_lcd(self):
        if not CharLCD: return None
        try:
            lcd = CharLCD("PCF8574", 0x27)
            lcd.clear()
            lcd.write_string("AquaGuardian v2")
            logger.info("✅ LCD initialized")
            return lcd
        except Exception as e:
            logger.error(f"LCD init failed: {e}")
            return None

    def display(self, line1: str, line2: str):
        if not self.lcd: return
        try:
            self.lcd.clear()
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(line1[:16])
            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string(line2[:16])
        except Exception:
            pass

    def cleanup(self):
        """Show shutdown message and blank the LCD."""
        if not self.lcd: return
        try:
            self.lcd.clear()
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string("  System Offline")
            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string("  Shutting down ")
            time.sleep(1.5)
            self.lcd.clear()
            self.lcd.backlight_enabled = False
        except Exception:
            pass

