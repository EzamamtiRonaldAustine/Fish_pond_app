# Raspberry Pi Deployment Guide (Railway Integration)

This guide explains how to connect your Raspberry Pi hardware to the live Railway API.

## 1. Prerequisites
- Raspberry Pi with Raspbian OS.
- Internet connectivity.
- Python 3.9+ installed.

## 2. Setting Up the Code
Copy the `pi/` directory to your Raspberry Pi:
```bash
# On your local machine (example)
scp -r ./pi/ pi@raspberrypi.local:~/pond_pi
```

## 3. Install Dependencies
On the Raspberry Pi, navigate to the folder and install the required libraries:
```bash
cd ~/pond_pi
pip install -r requirements_pi.txt
```

## 4. Configuration (Railway)
Create your environment file:
```bash
cp .env.example .env
nano .env
```

**Fill in the following values from your Railway Deployment:**

- `API_BASE_URL`: The URL of your Railway API (e.g., `https://your-api-url.up.railway.app/api`).
- `DEVICE_DB_ID`: The ID of your device in the database (usually `1`).
- `DEVICE_API_KEY`: The secret key set in your Railway environment variables (`DEVICE_API_KEY`).

## 5. Running the Agent
Start the hardware monitor:
```bash
python hardware_monitor.py
```

## 6. Real-Time Integration
- Once running, the Pi will start posting readings to Railway every 60 seconds (by default).
- You can check the `hardware_monitor.log` file for live status:
  ```bash
  tail -f hardware_monitor.log
  ```
- Go to your Railway Dashboard URL to see the live data visualizations.
