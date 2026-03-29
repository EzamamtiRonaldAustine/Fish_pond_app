# AquaGuardian v2.0 Modular Hardware Agent (`pi2`)

This directory contains the refactored, professional implementation of the Fish Pond Raspberry Pi agent. It has been redesigned from a monolithic script into a granular, modular system following professional software construction principles.

## Core Principles Applied
*   **Single Responsibility**: Each file handles exactly one component (e.g., one sensor, one actuator).
*   **No Magic Numbers**: All thresholds, timings, and GPIO pins are centralized in `config.py`.
*   **Decoupling**: Business logic (analysis) is separated from protocol logic (Modbus/GPIO).
*   **Robustness**: Thread-safe communication and independent error handling for each module.

## File Map

| File | Responsibility |
| :--- | :--- |
| **`main.py`** | **Orchestrator**: Entry point that starts background threads. |
| **`config.py`** | **Settings**: Holds all thresholds, GPIO maps, and timings. |
| **`analyzer.py`** | **Logic**: Evaluates sensor data and calculates quality scores. |
| **`sensor_rs485.py`** | **Probe**: Modbus driver for NPK, pH, and EC sensor. |
| **`sensor_ds18b20.py`** | **Temp**: 1-Wire driver for external temperature. |
| **`sensor_turbidity.py`**| **Turbidity**: GPIO driver for water clarity detection. |
| **`hardware_indicators.py`**| **Alerts**: Controls the Status LEDs and Buzzer. |
| **`hardware_pump.py`** | **Pump**: Manages the water pump relay and cycles. |
| **`hardware_lcd.py`** | **Display**: Drives the I2C 16x2 character display. |
| **`notifier_gsm.py`** | **SMS**: Handles emergency AT commands to the GSM module. |
| **`cloud_api.py`** | **Sync**: Handles Railway API and ThingSpeak communication. |

## Quick Start

1. **Environment**: Ensure the `.env` file exists in this folder (copied from `pi/.env`).
2. **Execute**: From the main project directory, run:
   ```bash
   python3 -m pi2.main
   ```

## Manual Creation (Nano Commands)

To create the files on your Raspberry Pi, run these commands one-by-one in your terminal. For each file, copy the content from VS Code, paste it into the nano editor, and press `Ctrl+O`, `Enter`, then `Ctrl+X` to save.

```bash
mkdir -p pi2 && cd pi2

nano __init__.py
nano config.py
nano analyzer.py
nano sensor_rs485.py
nano sensor_ds18b20.py
nano sensor_turbidity.py
nano hardware_indicators.py
nano hardware_pump.py
nano hardware_lcd.py
nano notifier_gsm.py
nano cloud_api.py
nano main.py
```

## Configuration
To change thresholds (e.g., when an alert triggers) or timing (e.g., SMS delay), edit **`pi2/config.py`**. Do not edit the logic files directly.
