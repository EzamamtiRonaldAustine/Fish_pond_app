# Fish Pond Monitoring System

A comprehensive IoT fish pond monitoring system with real-time water quality monitoring, hardware control, and web dashboard.

## Features

- **Real-time Monitoring**: Temperature, pH, EC, turbidity, nitrogen, phosphorus
- **Hardware Control**: Pump control, LED indicators, buzzer alerts
- **ML Integration**: Water quality prediction and anomaly detection
- **Web Dashboard**: Real-time data visualization and control interface
- **SMS Alerts**: Automated SMS notifications for critical conditions
- **API Backend**: RESTful API for data management and hardware control

## Railway Deployment

This project is configured for Railway deployment with separate services:

1. **API Service** (`api`) - Flask REST API with PostgreSQL database
2. **Dashboard Service** (`dashboard`) - Flask web dashboard
3. **Database** - PostgreSQL database managed by Railway

### Environment Variables Required

#### API Service
- `DB_NAME` - Railway PostgreSQL database name
- `DB_USER` - Railway PostgreSQL username  
- `DB_PASSWORD` - Railway PostgreSQL password
- `DB_HOST` - Railway PostgreSQL host
- `DB_PORT` - Railway PostgreSQL port
- `JWT_SECRET_KEY` - Secret for JWT token generation
- `DEVICE_API_KEY` - API key for hardware device authentication

#### Dashboard Service
- `API_BASE_URL` - URL of the deployed API service
- `JWT_SECRET_KEY` - Same as API service for authentication

### Hardware Configuration

For hardware deployment, update the Raspberry Pi `.env` file:
```
API_BASE_URL=https://your-app-name.railway.app/api
DEVICE_API_KEY=your_production_device_key
```

## Local Development

1. Install dependencies: `pip install -r requirements.txt`
2. Set up local PostgreSQL database
3. Run migrations in `database/` folder
4. Start API: `python run_api.py`
5. Start Dashboard: `python run_dashboard.py`
