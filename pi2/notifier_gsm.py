"""
pi2/notifier_gsm.py — GSM/SMS Notifier (SIM800C)
=================================================
Non-blocking init: the heavy serial handshake runs in a background
thread so the rest of the system can start immediately.
"""
import logging
import threading
import time

try:
    import serial
except ImportError:
    serial = None

from . import config as CFG

logger = logging.getLogger("GSMNotifier")


class GSMNotifier:
    def __init__(self):
        self._ser       = None
        self._lock      = threading.Lock()
        self._last_sent = 0.0
        self._ready     = False          # True once GSM is fully initialised

        if serial is None:
            logger.warning("pyserial not installed — GSM unavailable")
            return

        # Launch the slow serial handshake in the background
        t = threading.Thread(target=self._background_init, daemon=True)
        t.start()
        logger.info("GSM init started in background thread")

    # ── Background Initialisation ──────────────────────────────────────────
    def _background_init(self):
        """Runs in a daemon thread — opens serial, waits for SIM & network."""
        try:
            self._ser = serial.Serial(CFG.GSM_PORT, CFG.GSM_BAUDRATE, timeout=2)
            time.sleep(2)                          # Let SIM800C stabilise

            self._cmd("AT")                        # Check communication
            self._cmd("ATE0")                      # Disable echo

            # Wait for SIM card (up to ~12 s)
            for _ in range(3):
                if "READY" in self._cmd("AT+CPIN?", delay=2):
                    break
                time.sleep(2)

            # Wait for network registration (up to 60 s)
            start = time.time()
            while time.time() - start < 60:
                reply = self._cmd("AT+CREG?")
                if "+CREG: 0,1" in reply or "+CREG: 0,5" in reply:
                    break
                time.sleep(3)

            self._cmd("AT+CMGF=1")                 # SMS text mode
            self._cmd('AT+CSCS="GSM"')             # GSM character set
            self._ready = True
            logger.info("✅ GSM ready")

        except Exception as exc:
            logger.error(f"GSM init failed: {exc}")
            self._ser = None

    # ── Public API ─────────────────────────────────────────────────────────
    def send_sms(self, text: str) -> bool:
        """Send SMS to all configured numbers. Respects cooldown."""
        if not self._ready or not self._ser:
            return False
        now = time.time()
        if now - self._last_sent < CFG.SMS_COOLDOWN:
            return False

        success = False
        with self._lock:
            for number in CFG.SMS_PHONE_NUMBERS:
                number = number.strip()
                if not number:
                    continue
                try:
                    # Request send — wait for '>' prompt
                    reply = self._cmd(f'AT+CMGS="{number}"', delay=2)
                    if ">" not in reply:
                        logger.error(f"No prompt for {number}")
                        continue

                    # Send message + Ctrl+Z
                    self._ser.write(text.encode())
                    time.sleep(0.5)
                    self._ser.write(b"\x1A")

                    # Wait for confirmation (up to 20 s)
                    response = ""
                    for _ in range(20):
                        time.sleep(1)
                        response += self._ser.read_all().decode(errors="ignore")
                        if "+CMGS:" in response or "ERROR" in response:
                            break

                    if "+CMGS:" in response:
                        logger.info(f"✅ SMS sent to {number}")
                        success = True
                    else:
                        logger.error(f"❌ SMS failed to {number}")

                except Exception as exc:
                    logger.error(f"SMS error for {number}: {exc}")

        if success:
            self._last_sent = now
        return success

    # ── Internals ──────────────────────────────────────────────────────────
    def _cmd(self, command: str, delay: float = 1.0) -> str:
        """Send an AT command and return the response."""
        try:
            self._ser.write((command + "\r\n").encode())
            time.sleep(delay)
            return self._ser.read_all().decode(errors="ignore")
        except Exception as exc:
            logger.error(f"AT error ({command}): {exc}")
            return ""
