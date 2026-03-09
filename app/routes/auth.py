from flask import session, g, request, jsonify, Blueprint
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash, check_password_hash
import math

from app.connection import get_db
from config import Config

auth_bp = Blueprint('auth', __name__)


# 1. Interceptor: Executes before each request reaches a route
@auth_bp.before_request
def load_logged_in_user():
    """
    Checks if a user ID exists in the session.
    If it exists, queries user details from the MySQL database and attaches them to g.user.
    """
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        engine = get_db()
        with engine.connect() as conn:
            query = text("""
                SELECT user_id, full_name, preferred_language, created_at 
                FROM users 
                WHERE user_id = :user_id
            """)
            result = conn.execute(query, {"user_id": user_id}).fetchone()

            if result:
                # Convert result to dictionary for easier access
                g.user = dict(result._mapping)
            else:
                g.user = None


# 2. Login Route: Authentication and session handling
@auth_bp.route('/login', methods=['POST'])
def login():
    user_id = request.form.get('user_id')
    password = request.form.get('password')

    if not user_id or not password:
        return jsonify({'error': 'Missing credentials'}), 400

    engine = get_db()
    with engine.connect() as conn:
        query = text("SELECT password_hash FROM users WHERE user_id = :user_id")
        result = conn.execute(query, {"user_id": user_id}).fetchone()

        # Verify the hashed password
        if result and check_password_hash(result._mapping['password_hash'], password):
            session.permanent = True
            session['user_id'] = user_id  # Store the identifier in the session
            return jsonify({'message': 'Login successful!'})

    return jsonify({'error': 'Invalid credentials'}), 401


@auth_bp.route('/logout')
def logout():
    if g.user is None:
        return jsonify({'error': 'Please log in first'}), 401

    session.pop('user_id', None)
    return jsonify({'message': 'Successfully logged out'})


# 4. Registration Route: Create new user
@auth_bp.route('/register', methods=['POST'])
def register():
    user_id = request.form.get('user_id')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    preferred_language = request.form.get('preferred_language', 'en')

    if not user_id or not password:
        return jsonify({'error': 'user_id and password are required'}), 400

    if not full_name:
        full_name = user_id  # Default to ID if no name is provided

    # Hash the password for security
    hashed_pw = generate_password_hash(password)

    engine = get_db()
    with engine.connect() as conn:
        check_query = text("SELECT user_id FROM users WHERE user_id = :user_id")
        existing_user = conn.execute(check_query, {"user_id": user_id}).fetchone()

        if existing_user:
            return jsonify({'error': 'User ID already exists'}), 409

        insert_query = text("""
            INSERT INTO users (user_id, full_name, password_hash, preferred_language)
            VALUES (:user_id, :full_name, :password_hash, :preferred_language)
        """)

        conn.execute(insert_query, {
            "user_id": user_id,
            "full_name": full_name,
            "password_hash": hashed_pw,
            "preferred_language": preferred_language
        })

    return jsonify({'message': 'Registration successful!'}), 201










