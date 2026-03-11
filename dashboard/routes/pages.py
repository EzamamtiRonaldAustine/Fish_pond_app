from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..api_client import login_api, signup_api
import os

pages_bp = Blueprint('pages', __name__)

@pages_bp.route("/")
def home():
    return render_template("home.html")

@pages_bp.route("/about")
def about_page():
    return render_template("about.html")

@pages_bp.route("/contact")
def contact_page():
    return render_template("contact.html")

@pages_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        result = login_api(username, password)
        
        if 'access_token' in result:
            session['token'] = result['access_token']
            session['user'] = result['user']
            return redirect(url_for('dashboard.dashboard'))
        else:
            return render_template("login.html", 
                                 error=result.get('error', 'Login failed'),
                                 google_client_id=os.environ.get("GOOGLE_CLIENT_ID"))
            
    return render_template("login.html", google_client_id=os.environ.get("GOOGLE_CLIENT_ID"))

@pages_bp.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        full_name = request.form.get("full_name")
        organization_id = request.form.get("organization_id")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not all([username, email, full_name, organization_id, password, confirm_password]):
            return render_template("signup.html", error="All fields are required.")

        if password != confirm_password:
            return render_template("signup.html", error="Passwords do not match.")

        result = signup_api(
            username=username,
            password=password,
            email=email,
            full_name=full_name,
            organization_id=organization_id,
        )

        if 'access_token' in result:
            # Auto-login new farmer and redirect to dashboard
            session['token'] = result['access_token']
            session['user'] = result.get('user')
            flash("Registration successful. Welcome to your dashboard!", "success")
            return redirect(url_for("dashboard.dashboard"))

        return render_template("signup.html", 
                             error=result.get("error", "Registration failed."),
                             google_client_id=os.environ.get("GOOGLE_CLIENT_ID"))

    return render_template("signup.html", google_client_id=os.environ.get("GOOGLE_CLIENT_ID"))

@pages_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('pages.home'))

@pages_bp.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")
