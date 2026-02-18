# api/extensions.py
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_cors import CORS

jwt      = JWTManager()
socketio = SocketIO()
cors     = CORS()