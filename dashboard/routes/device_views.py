from flask import Blueprint, render_template, session, redirect, url_for

devices_bp = Blueprint('devices', __name__)

@devices_bp.route("/devices")
def devices_page():
    if not session.get('token'):
        return redirect(url_for('pages.login_page'))
    return render_template("devices.html")
