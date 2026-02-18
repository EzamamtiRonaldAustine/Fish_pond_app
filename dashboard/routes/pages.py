from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..api_client import login_api

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
        # Signup logic is handled via API call in the frontend JS or here?
        # The provided user code had JS fetch for signup.
        # But for consistency, let's keep GET here.
        pass
    return render_template("signup.html")

@pages_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('pages.home'))
