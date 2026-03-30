"""
pi2/main.py — Multi-threaded Hardware Orchestrator
==================================================
The main entry point for the AquaGuardian v2.0 modular system.
Execute this file on the Raspberry Pi: python3 -m pi2.main
"""
import logging
import threading
import time
import signal
import sys

# Modular Imports
try:
    from . import config as CFG
    from .sensor_rs485 import RS485Sensor
    from .sensor_ds18b20 import DS18B20Sensor
    from .sensor_turbidity import TurbiditySensor
    from .analyzer import WaterQualityAnalyzer
    from .hardware_indicators import IndicatorController
    from .hardware_pump import PumpController
    from .hardware_lcd import LCDController
    from .notifier_gsm import GSMNotifier
    from .cloud_api import CloudClient
except ImportError:
    # Allow running directly if not as a package module
    import config as CFG
    from sensor_rs485 import RS485Sensor
    from sensor_ds18b20 import DS18B20Sensor
    from sensor_turbidity import TurbiditySensor
    from analyzer import WaterQualityAnalyzer
    from hardware_indicators import IndicatorController
    from hardware_pump import PumpController
    from hardware_lcd import LCDController
    from notifier_gsm import GSMNotifier
    from cloud_api import CloudClient

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("Main")

class AquaGuardianAgent:
    def __init__(self):
        self._running = True
        
        # Initialize GPIO Mode (Must be done before any sensors/actuators call GPIO.setup)
        try:
            import RPi.GPIO as GPIO
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            logger.info("✅ GPIO mode set to BCM")
        except ImportError:
            GPIO = None
            logger.warning("⚠️ RPi.GPIO not found, running in simulation mode")

        # Initialize Components
        self.rs485      = RS485Sensor()
        self.temp_ext   = DS18B20Sensor()
        self.turbid_sen = TurbiditySensor()
        self.analyzer   = WaterQualityAnalyzer()
        self.indicators = IndicatorController()
        self.pump       = PumpController()
        self.lcd        = LCDController()
        self.gsm        = GSMNotifier()
        self.cloud      = CloudClient()

        self._print_header()

        # State tracking
        self.latest_data = {}
        self.latest_assessment = {"overall": "GOOD", "score": 0}
    def _print_header(self):
        print("\n" + "="*60)
        print("AQUAGUARDIAN v2.0 — Modular Hardware Agent")
        print(f"API Target : {CFG.API_BASE_URL}")
        print(f"Device ID  : {CFG.DEVICE_DB_ID}")
        print("="*60 + "\n")

    def _monitor_loop(self):
        """Primary sensor acquisition and local logic loop."""
        while self._running:
            try:
                # 1. Read Raw Data
                data = self.rs485.read_all()
                ext_temp = self.temp_ext.read_temp()
                is_turbid = self.turbid_sen.is_turbid()

                # 2. Refine & Analyze
                if ext_temp: data["temperature"] = ext_temp
                assessment = self.analyzer.assess(data, is_turbid)
                self.latest_data = data
                self.latest_assessment = assessment

                # Compact Log (Matches old style)
                logger.info(f"[Monitor] status={assessment['overall']} score={assessment['score']} "
                            f"temp={data.get('temperature', 'None')} pH={data.get('ph', 'None')}")

                # 3. Local Hardware Actions
                self.indicators.set_status(assessment["overall"])
                self.pump.tick()
                
                # Auto-Pump logic
                if assessment["overall"] == "CRITICAL" and not self.pump.is_running:
                    self.pump.start("NORMAL")

                # LCD Refresh
                self.lcd.display(
                    f"Stat: {assessment['overall']}",
                    f"Score: {assessment['score']}"
                )

                # 4. Sustained Alert Logic
                if assessment["overall"] == "CRITICAL":
                    if not self._critical_start: self._critical_start = time.time()
                    elif time.time() - self._critical_start >= CFG.CRITICAL_DURATION:
                        alerts_text = " | ".join(assessment.get("alerts", []))
                        sms_msg = f"🚨 CRITICAL Alert! Score: {assessment['score']}\n"
                        if alerts_text:
                            sms_msg += f"Issues: {alerts_text}\n"
                        sms_msg += "Pump is actively running to improve water quality."
                        self.gsm.send_sms(sms_msg)
                else:
                    self._critical_start = None

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            # Use short sleeps to allow quick, clean exit
            for _ in range(int(CFG.SENSOR_READ_INTERVAL)):
                if not self._running: return
                time.sleep(1)

    def _cloud_loop(self):
        """Communication loop for the Railway API."""
        while self._running:
            try:
                if self.latest_data:
                    self.cloud.post_data(
                        self.latest_data,
                        self.latest_assessment["overall"],
                        self.latest_assessment["score"],
                        self.turbid_sen.is_turbid(),
                        self.latest_assessment.get("alerts", [])
                    )
            except Exception as e:
                logger.error(f"Cloud loop error: {e}")

            # Use short sleeps to allow quick, clean exit
            for _ in range(int(CFG.API_SEND_INTERVAL)):
                if not self._running: return
                time.sleep(1)

    def _command_loop(self):
        """Poll for remote commands from the web UI."""
        while self._running:
            try:
                cmds = self.cloud.fetch_commands()
                for c in cmds:
                    cmd_type = c.get("command", "").upper()
                    if cmd_type == "PUMP_ON": self.pump.start()
                    elif cmd_type == "PUMP_OFF": self.pump.stop()
                    elif cmd_type == "CLEAR_ALERT": self.indicators.silence()
            except Exception:
                pass
            time.sleep(CFG.COMMAND_POLL_INTERVAL)

    def run(self):
        logger.info("Starting background threads...")
        threads = [
            ("Monitor", self._monitor_loop),
            ("Cloud",   self._cloud_loop),
            ("Commands", self._command_loop),
        ]
        
        for name, target in threads:
            t = threading.Thread(target=target, daemon=True)
            t.start()
            logger.info(f"Thread started: {name}")

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received — shutting down")
        finally:
            self.stop()

    def stop(self):
        if not self._running: return
        logger.info("Stopping hardware agent...")
        self._running = False

        # 1. Stop pump safely (force relay HIGH)
        try: self.pump.stop()
        except: pass

        # 2. Show offline message on LCD
        try: self.lcd.cleanup()
        except: pass

        # 3. Stop PWM buzzer BEFORE GPIO.cleanup() — this is what prevents the segfault
        try: self.indicators.cleanup()
        except: pass

        # 4. Now safe to release all GPIO pins
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
            logger.info("GPIO and LCD cleaned up")
        except:
            pass

        logger.info("Hardware agent stopped.")

if __name__ == "__main__":
    agent = AquaGuardianAgent()

    def _handle_signal(signum, frame):
        logger.info(f"Signal {signum} received — initiating shutdown")
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    agent.run()
