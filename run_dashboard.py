from dashboard import create_app
from dashboard.config import Config

app = create_app()

if __name__ == '__main__':
    print(f"Starting Dashboard on port {Config.DASHBOARD_PORT}")
    app.run(host='0.0.0.0', port=Config.DASHBOARD_PORT, debug=True)