# run_unified.py
import os
from flask import Flask, jsonify
from flask_socketio import SocketIO
from api import create_app as create_api_app
from api.extensions import socketio, cors, jwt
from dashboard import create_app as create_dashboard_app

# Create the main app container
app = Flask(__name__, 
            static_folder='dashboard/static', 
            template_folder='dashboard/templates')

# 1. Load Configurations
from api.config import Config as ApiConfig
from dashboard.config import Config as DashboardConfig
app.config.from_object(ApiConfig)
app.config.from_object(DashboardConfig)

# 2. Initialize Shared extensions
jwt.init_app(app)
cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
socketio.init_app(app, cors_allowed_origins="*", async_mode='eventlet')

# 3. Register API Blueprints
from api.routes.auth import auth_bp
from api.routes.users import users_bp
from api.routes.devices import devices_bp
from api.routes.sensors import sensors_bp
from api.routes.alerts import alerts_bp
from api.routes.organizations import organizations_bp
from api.routes.health import health_bp
from api.routes.control import control_bp
from api.routes.contact import contact_bp

app.register_blueprint(auth_bp,          url_prefix='/api/auth')
app.register_blueprint(users_bp,         url_prefix='/api')
app.register_blueprint(devices_bp,       url_prefix='/api')
app.register_blueprint(sensors_bp,       url_prefix='/api')
app.register_blueprint(alerts_bp,        url_prefix='/api')
app.register_blueprint(organizations_bp, url_prefix='/api')
app.register_blueprint(health_bp,        url_prefix='/api')
app.register_blueprint(control_bp,       url_prefix='/api')
app.register_blueprint(contact_bp,       url_prefix='/api')

# 4. Register Dashboard Blueprints
from dashboard.routes.pages import pages_bp
from dashboard.routes.dashboard_views import dashboard_bp
from dashboard.routes.device_views import devices_bp as dash_devices_bp
from dashboard.routes.user_views import users_bp as dash_users_bp
from dashboard.routes.proxy import proxy_bp
from dashboard.routes.ml_routes import ml_bp
from dashboard.routes.control_views import control_views_bp

app.register_blueprint(pages_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(dash_devices_bp)
app.register_blueprint(dash_users_bp)
app.register_blueprint(proxy_bp)
app.register_blueprint(ml_bp)
app.register_blueprint(control_views_bp)

# 5. Add Uptime/Ping Route
@app.route("/ping")
def ping():
    return jsonify({"status": "active", "message": "Stay awake!"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting Unified Fish Pond System on port {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
