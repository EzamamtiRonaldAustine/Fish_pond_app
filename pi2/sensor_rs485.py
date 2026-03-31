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
            logger.info("✅ RS485 sensor initialized")
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
            # Temperature — raw integer / 10 (e.g. 245 → 24.5°C)
            temp = self._read_reg(self._REGISTERS["temperature"], decimals=1)
            data["temperature"] = temp

            # pH — raw integer / 10 (e.g. 35 → 3.5, 70 → 7.0)
            # This sensor outputs value * 10 (not * 100)
            raw_ph = self._read_reg(self._REGISTERS["ph"], decimals=0)
            if raw_ph and raw_ph > 5:   # sanity check: raw > 5 means pH > 0.5
                data["ph"] = round(raw_ph / 10.0, 2)
            else:
                data["ph"] = None

            # EC — raw integer / 10 (µS/cm)
            data["ec"] = self._read_reg(self._REGISTERS["ec"], decimals=1)

            # NPK — raw integer / 10 (mg/kg) — matches original sensor behaviour
            for p in ("nitrogen", "phosphorus", "potassium"):
                data[p] = self._read_reg(self._REGISTERS[p], decimals=1)

            self._error_count = 0
            return data
        except Exception as exc:
            self._error_count += 1
            logger.error(f"RS485 read error #{self._error_count}: {exc}")
            if self._error_count >= 5:
                self.instrument = self._init_rs485()
                self._error_count = 0
            return {}

    def _read_reg(self, reg: int, decimals: int = 1) -> float | None:
        """Read a single Modbus register. decimals controls fixed-point scaling."""
        try:
            return self.instrument.read_register(reg, decimals, functioncode=3)
        except Exception:
            return None
