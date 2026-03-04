from flask import Blueprint, render_template

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login")
def login():
    # Renders app/templates/auth/login.html
    return render_template("auth/login.html")