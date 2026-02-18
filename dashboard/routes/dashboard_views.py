from flask import Blueprint, render_template

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@dashboard_bp.route("/history")
def history():
    return render_template("history.html")

@dashboard_bp.route("/alerts")
def alerts_page():
    return render_template("alerts.html")
