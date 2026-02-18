from flask import Blueprint, render_template

devices_bp = Blueprint('devices', __name__)

@devices_bp.route("/devices")
def devices_page():
    return render_template("devices.html")
