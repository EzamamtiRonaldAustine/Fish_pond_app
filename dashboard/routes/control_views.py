"""
dashboard/routes/control_views.py — Hardware Control Page
==========================================================
Serves the /control page and protects it so only admin and farmer
users can access hardware control features.
"""
from flask import Blueprint, render_template, redirect, url_for, session
import logging

control_views_bp = Blueprint("control_views", __name__)
logger = logging.getLogger(__name__)


def _require_control_access():
    """
    Return the current user dict if they have control access (admin/farmer),
    otherwise return None (caller should redirect/403).
    """
    if "user" not in session:
        return None
    user = session["user"]
    if user.get("role") not in ("admin", "farmer"):
        return None
    return user


@control_views_bp.route("/control")
def control_page():
    """
    Hardware control and visualisation page.
    Restricted to authenticated admin and farmer users.
    """
    user = _require_control_access()
    if user is None:
        if "user" not in session:
            return redirect(url_for("pages.login_page"))
        # Logged in but wrong role — show 403 via dashboard with message
        return redirect(url_for("dashboard.dashboard", error="access_denied"))

    return render_template(
        "control.html",
        user=user,
        page_title="Hardware Control Centre",
    )
