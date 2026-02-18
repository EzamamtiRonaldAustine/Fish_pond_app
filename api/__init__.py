# api/__init__.py
from flask import Flask
from .config import Config
from .extensions import jwt, socketio, cors
from .routes.auth import auth_bp
from .routes.users import users_bp
from .routes.devices import devices_bp
from .routes.sensors import sensors_bp
from .routes.alerts import alerts_bp
from .routes.organizations import organizations_bp
from .routes.health import health_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')

    # Register all route groups (called "Blueprints")
    app.register_blueprint(auth_bp,          url_prefix='/api/auth')
    app.register_blueprint(users_bp,         url_prefix='/api')
    app.register_blueprint(devices_bp,       url_prefix='/api')
    app.register_blueprint(sensors_bp,       url_prefix='/api')
    app.register_blueprint(alerts_bp,        url_prefix='/api')
    app.register_blueprint(organizations_bp, url_prefix='/api')
    app.register_blueprint(health_bp,        url_prefix='/api')

    return app