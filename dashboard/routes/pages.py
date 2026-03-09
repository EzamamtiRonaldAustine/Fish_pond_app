from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..api_client import login_api, signup_api

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
            return render_template("login.html", error=result.get('error', 'Login failed'))
            
    return render_template("login.html")

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
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("pages.login_page"))

        return render_template("signup.html", error=result.get("error", "Registration failed."))

    return render_template("signup.html")

@pages_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('pages.home'))
