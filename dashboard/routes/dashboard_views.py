from flask import Blueprint, render_template, session, redirect, url_for

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route("/dashboard")
def dashboard():
    if not session.get('token'):
        return redirect(url_for('pages.login_page'))
    return render_template("dashboard.html")

@dashboard_bp.route("/history")
def history():
    if not session.get('token'):
        return redirect(url_for('pages.login_page'))
    return render_template("history.html")

@dashboard_bp.route("/alerts")
def alerts_page():
    if not session.get('token'):
        return redirect(url_for('pages.login_page'))
    return render_template("alerts.html")
