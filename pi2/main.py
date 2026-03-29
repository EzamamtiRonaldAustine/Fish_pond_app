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

        # State tracking
        self.latest_data = {}
        self.latest_assessment = {"overall": "GOOD", "score": 0}
        self._critical_start = None

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
                        self.gsm.send_sms(f"🚨 CRITICAL sustained alert! Score: {assessment['score']}")
                else:
                    self._critical_start = None

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            time.sleep(CFG.SENSOR_READ_INTERVAL)

    def _cloud_loop(self):
        """Communication loop for the Railway API."""
        while self._running:
            try:
                if self.latest_data:
                    self.cloud.post_data(
                        self.latest_data,
                        self.latest_assessment["overall"],
                        self.latest_assessment["score"]
                    )
            except Exception as e:
                logger.error(f"Cloud loop error: {e}")
            time.sleep(CFG.API_SEND_INTERVAL)

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
        logger.info("Modular Hardware Agent starting...")
        threads = [
            threading.Thread(target=self._monitor_loop, daemon=True),
            threading.Thread(target=self._cloud_loop,   daemon=True),
            threading.Thread(target=self._command_loop, daemon=True),
        ]
        for t in threads: t.start()

        try:
            while self._running: time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        logger.info("Shutting down...")
        self._running = False
        self.pump.stop()
        self.indicators._reset_indicators()
        logger.info("Agent stopped.")

if __name__ == "__main__":
    agent = AquaGuardianAgent()
    agent.run()
