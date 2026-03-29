"""
pi2/sensor_rs485.py — RS485 Modbus Sensor Driver
===============================================
Handles communication with the 7-in-1 multi-parameter probe.
"""
import logging
import time
import minimalmodbus
from . import config as CFG

logger = logging.getLogger("RS485Sensor")

class RS485Sensor:
    """Driver for the RS485 Modbus RTU multi-parameter probe."""
    
    _REGISTERS = {
        "temperature": 19,
        "ph":          13,
        "ec":           7,
        "nitrogen":     4,
        "phosphorus":   5,
        "potassium":    6,
    }

    def __init__(self):
        self._error_count = 0
        self.instrument = self._init_rs485()

    def _init_rs485(self):
        try:
            inst = minimalmodbus.Instrument(CFG.RS485_PORT, CFG.RS485_SLAVE_ID)
            inst.serial.baudrate = 9600
            inst.serial.timeout  = 1
            return inst
        except Exception as exc:
            logger.error(f"RS485 initialization failed: {exc}")
            return None

    def read_all(self) -> dict:
        """Read all parameters. Returns dict of findings."""
        if not self.instrument:
            return {}

        data = {}
        try:
            # Basic readings
            temp = self._read_reg(self._REGISTERS["temperature"])
            data["temperature"] = temp
            
            raw_ph = self._read_reg(self._REGISTERS["ph"])
            if raw_ph and raw_ph > 0.5:
                # Apply pH calibration and temp compensation
                ph = raw_ph / 3.13
                data["ph"] = round(ph - ( (temp or 25.0) - 25) * 0.01, 2)
            else:
                data["ph"] = None

            for p in ("ec", "nitrogen", "phosphorus", "potassium"):
                data[p] = self._read_reg(self._REGISTERS[p])

            self._error_count = 0
            return data
        except Exception as exc:
            self._error_count += 1
            logger.error(f"RS485 read error #{self._error_count}: {exc}")
            if self._error_count >= 5:
                self.instrument = self._init_rs485()
                self._error_count = 0
            return {}

    def _read_reg(self, reg: int) -> float | None:
        try:
            return self.instrument.read_register(reg, 1, functioncode=3)
        except Exception:
            return None
