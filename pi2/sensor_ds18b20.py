"""
pi2/sensor_ds18b20.py — 1-Wire Temperature Sensor Driver
========================================================
"""
import glob
import logging
import os

logger = logging.getLogger("DS18B20")

class DS18B20Sensor:
    def __init__(self):
        self.device_file = self._find_device()

    def _find_device(self) -> str | None:
        try:
            # Ensure 1-wire modules are loaded (typical for Pi)
            os.system("modprobe w1-gpio")
            os.system("modprobe w1-therm")
            files = glob.glob("/sys/bus/w1/devices/28-*")
            if files:
                dev = files[0] + "/w1_slave"
                logger.info(f"✅ DS18B20 initialized: {dev}")
                return dev
        except Exception as e:
            logger.error(f"Failed to find DS18B20: {e}")
        return None

    def read_temp(self) -> float | None:
        if not self.device_file:
            return None
        try:
            with open(self.device_file, 'r') as f:
                lines = f.readlines()
            if "YES" in lines[0] and "t=" in lines[1]:
                temp_string = lines[1].split("t=")[1]
                temp_c = float(temp_string) / 1000.0
                return temp_c
        except Exception as e:
            logger.debug(f"DS18B20 read failed: {e}")
        return None
