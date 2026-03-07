from dashboard import create_app
from dashboard.config import Config
import os

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', Config.DASHBOARD_PORT))
    print(f"Starting Dashboard on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)