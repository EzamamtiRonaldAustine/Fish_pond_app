"""
pi2/sensor_rs485.py — RS485 Modbus Sensor Driver
===============================================
Handles communication with the 7-in-1 multi-parameter probe.

pH Calibration
--------------
The probe's pH register returns a raw value that must be:
  1. Divided by 10 (done by minimalmodbus via decimals=1)
  2. Divided again by a calibration constant (3.13)
  3. Temperature-compensated (-0.01 pH per °C above 25)
This matches the original proven pipeline from hardware_monitor.py.

Noise Filtering
---------------
The probe occasionally returns garbage pH readings during warm-up
or bus collisions. A rolling median filter with consistency gating
ensures only stable values reach the analyzer.
"""
import logging
import time
from collections import deque

import minimalmodbus
from . import config as CFG

logger = logging.getLogger("RS485Sensor")

# ── pH filter constants ────────────────────────────────────────────────────
_PH_MIN         = 2.0       # Lowest plausible pH for a fish pond
_PH_MAX         = 12.0      # Highest plausible pH for a fish pond
_PH_BUFFER_SIZE = 5         # Rolling window for median
_PH_MAX_SPREAD  = 2.0       # Max (max-min) in buffer to consider stable
_PH_CAL_DIVISOR = 3.13      # Calibration constant from original codebase


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
        self._error_count  = 0
        self._ph_buffer    = deque(maxlen=_PH_BUFFER_SIZE)
        self._last_good_ph = None        # last value that passed all filters
        self.instrument    = self._init_rs485()

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

    # ── Public API ──────────────────────────────────────────────────────────
    def read_all(self) -> dict:
        """Read all parameters. Returns dict of findings."""
        if not self.instrument:
            return {}

        data = {}
        try:
            # Temperature — raw / 10 (e.g. 245 → 24.5°C)
            temp = self._read_reg(self._REGISTERS["temperature"], decimals=1)
            data["temperature"] = temp

            # pH — calibrated & filtered (see _calc_ph + _filter_ph)
            raw_ph = self._read_reg(self._REGISTERS["ph"], decimals=1)
            calibrated_ph = self._calc_ph(raw_ph, temp)
            data["ph"] = self._filter_ph(calibrated_ph, raw_ph)

            # EC — raw / 10 (µS/cm)
            data["ec"] = self._read_reg(self._REGISTERS["ec"], decimals=1)

            # NPK — raw / 10 (mg/kg)
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

    # ── pH Calibration (matches original hardware_monitor.py) ───────────────
    @staticmethod
    def _calc_ph(raw_value: float | None, temperature: float | None) -> float | None:
        """
        Convert raw register value to calibrated, temperature-compensated pH.

        Pipeline (proven in original codebase):
          1. minimalmodbus already divided raw register by 10  (decimals=1)
          2. Divide again by calibration constant (3.13)
          3. Temperature-compensate: −0.01 pH per °C above 25
        """
        if raw_value is None or raw_value <= 0:
            return None

        ph = raw_value / _PH_CAL_DIVISOR
        temp = temperature if temperature is not None else 25.0
        compensated = ph - (temp - 25.0) * 0.01
        return round(compensated, 2)

    # ── pH Noise Filter ─────────────────────────────────────────────────────
    def _filter_ph(self, ph_val: float | None, raw_val: float | None) -> float | None:
        """
        Three-stage filter for noisy pH probe:

        1. Range gate   — discard anything outside 2.0–12.0
        2. Buffer       — store valid readings in a rolling window
        3. Stability    — only report the median when readings agree
                          (spread < 2.0 pH across the window)

        Falls back to last known-good value during noise bursts.
        """
        if ph_val is None:
            return self._last_good_ph

        # Stage 1: range gate
        if not (_PH_MIN <= ph_val <= _PH_MAX):
            logger.warning(f"pH rejected (out of range): {ph_val:.2f} (raw_reg={raw_val})")
            return self._last_good_ph

        # Stage 2: add to rolling buffer
        self._ph_buffer.append(ph_val)

        # Stage 3: stability check — need ≥3 readings that agree
        if len(self._ph_buffer) < 3:
            logger.debug(f"pH buffering: {ph_val:.2f} ({len(self._ph_buffer)}/{_PH_BUFFER_SIZE})")
            return self._last_good_ph

        spread = max(self._ph_buffer) - min(self._ph_buffer)
        if spread > _PH_MAX_SPREAD:
            logger.warning(
                f"pH unstable (spread={spread:.1f}): "
                f"buffer={[round(v, 1) for v in self._ph_buffer]}"
            )
            return self._last_good_ph

        # All checks passed — report the median
        median_ph = sorted(self._ph_buffer)[len(self._ph_buffer) // 2]
        self._last_good_ph = median_ph
        return median_ph

    # ── Internals ───────────────────────────────────────────────────────────
    def _read_reg(self, reg: int, decimals: int = 1) -> float | None:
        """Read a single Modbus register. decimals controls fixed-point scaling."""
        try:
            return self.instrument.read_register(reg, decimals, functioncode=3)
        except Exception:
            return None
