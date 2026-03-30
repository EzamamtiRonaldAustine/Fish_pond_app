"""
pi2/notifier_gsm.py — GSM/SMS Emergency Notifier
===============================================
"""
import logging
import threading
import time
import serial
from datetime import datetime
from . import config as CFG

logger = logging.getLogger("GSMNotifier")

class GSMNotifier:
    def __init__(self):
        self._ser = self._init_gsm()
        self._last_sent = 0

    def _init_gsm(self):
        try:
            ser = serial.Serial(CFG.GSM_PORT, CFG.GSM_BAUDRATE, timeout=5)
            ser.write(b"AT\r\n")
            time.sleep(0.5)
            ser.write(b"AT+CMGF=1\r\n") # Text mode
            logger.info("✅ GSM module initialized")
            return ser
        except Exception as e:
            logger.error(f"GSM init failed: {e}")
            return None

    def send_sms(self, text: str):
        if not self._ser: return
        now = time.time()
        if now - self._last_sent < CFG.SMS_COOLDOWN: return
        
        for num in CFG.SMS_PHONE_NUMBERS:
            try:
                self._ser.write(f'AT+CMGS="{num.strip()}"\r\n'.encode())
                time.sleep(1)
                self._ser.write(text.encode())
                self._ser.write(b"\x1A") # Ctrl+Z
                time.sleep(3)
                logger.info(f"SMS sent to {num}")
            except Exception as e:
                logger.error(f"SMS failed to {num}: {e}")
        
        self._last_sent = now
