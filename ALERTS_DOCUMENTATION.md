# AquaGuardian Alert System Documentation

This document explains the correlation and behavior of the multi-tiered alert system in the AquaGuardian fish pond application. 

The system uses a single source of truth (the Raspberry Pi's local `WaterQualityAnalyzer`) to determine the pond's health status, but it deploys alerts across different channels using different timing strategies to balance immediate logging with emergency notification.

## Alert Correlation Matrix

| Feature | Primary Component | Trigger Condition | Timing / Delay | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Local LED/Buzzer** | `HardwareController` (RPi) | Status changes to `WARNING` or `CRITICAL` | **Instant** | Local visual and audio warning for on-site staff. |
| **Dashboard Alerts** | Web API (`sensors.py`) & PostgreSQL | `quality_status == "CRITICAL"` received from Pi | **Instant** | Permanent logging of critical events; immediate display on the web interface. |
| **Hardware Pump Control** | `HardwareController` (RPi) | Average Temps/pH exceed safe bounds or high Turbidity | **Instant** | Automated physical mitigation (water exchange or aeration). |
| **GSM SMS Alerts** | `SMSNotifier` (RPi GSM Module) | Status remains `CRITICAL` for sustained period | **Delayed** (`120 seconds / 2 minutes`) | Emergency remote notification. Delayed to prevent spam from transient sensor noise. |

## Detailed Breakdown

### 1. The Trigger (The "Brain")
Every read cycle (`CFG.SENSOR_READ_INTERVAL`), the Raspberry Pi (`pi/hardware_monitor.py`) calculates a cumulative `quality_score` based on the sensor readings (Temperature, pH, EC, NPK, Turbidity).
* If the score hits specific thresholds from `config.py`, the pond status is flagged as **WARNING** or **CRITICAL**.
* The analyzer generates specific alert messages (e.g., "🚨 CRITICAL: pH 10.5 dangerously alkaline").

### 2. Web Dashboard Alerts (Instant Logging)
*   As soon as the Pi detects a CRITICAL state, it includes this status in its next data payload to the cloud API (`/api/sensors/readings`).
*   The backend database immediately automatically duplicates this critical state into an explicit `alerts` table.
*   **Correlation**: The web dashboard reads from this table, meaning what you see online is a near-instant reflection of the hardware's internal assessment.

### 3. GSM SMS Alerts (Sustained Emergency)
*   The hardware handles SMS natively using a dedicated `_sms_loop` thread.
*   **Sustained Timer**: When a CRITICAL state is detected, a timer starts (`_critical_start`). An SMS is *not* sent immediately. This prevents a fish bumping a sensor from waking you up at 3 AM.
*   **Execution**: If the CRITICAL state persists continuously for the `CRITICAL_DURATION` (**120 seconds / 2 minutes**), the Pi issues an AT command to the GSM module, sending an SMS to your configured phone numbers.
*   **Cooldown**: After a successful SMS, a cooldown period `SMS_COOLDOWN` (**120 seconds / 2 minutes**) enforces silence to avoid draining prepaid SIM credit.
