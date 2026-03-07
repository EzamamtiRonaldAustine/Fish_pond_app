# run_api.py
from api import create_app
from api.extensions import socketio
import os

app = create_app()

if __name__ == '__main__':
    # Use production-ready server for Railway deployment
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)