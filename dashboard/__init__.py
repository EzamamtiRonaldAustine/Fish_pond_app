from flask import Flask
from .config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from .routes.pages import pages_bp
    from .routes.dashboard_views import dashboard_bp
    from .routes.device_views import devices_bp
    from .routes.user_views import users_bp
    from .routes.proxy import proxy_bp
    from .routes.ml_routes import ml_bp
    from .routes.control_views import control_views_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(devices_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(proxy_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(control_views_bp)

    return app
