from flask import session, g, request, jsonify, Blueprint, render_template, redirect, url_for
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
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    user_id = request.form.get('user_id')
    password = request.form.get('password')

    if not user_id or not password:
        return render_template('login.html', error='Missing credentials')

    engine = get_db()
    with engine.connect() as conn:
        query = text("SELECT password_hash FROM users WHERE user_id = :user_id")
        result = conn.execute(query, {"user_id": user_id}).fetchone()

        # Verify the hashed password
        if result and check_password_hash(result._mapping['password_hash'], password):
            session.permanent = True
            session['user_id'] = user_id  # Store the identifier in the session
            return redirect(url_for('main.home'))

    return render_template('login.html', error='Invalid credentials')


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('main.home'))


# 4. Registration Route: Create new user
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    user_id = request.form.get('user_id')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    preferred_language = request.form.get('preferred_language', 'en')

    if not user_id or not password:
        return render_template('register.html', error='user_id and password are required')

    if not full_name:
        full_name = user_id  # Default to ID if no name is provided

    # Hash the password for security
    hashed_pw = generate_password_hash(password)

    engine = get_db()
    with engine.connect() as conn:
        check_query = text("SELECT user_id FROM users WHERE user_id = :user_id")
        existing_user = conn.execute(check_query, {"user_id": user_id}).fetchone()

        if existing_user:
            return render_template('register.html', error='User ID already exists')

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

    return redirect(url_for('auth.login'))








# User Favorites CRUD Functionality


# 1. Add to Favorites
@auth_bp.route('/favorites', methods=['POST'])
def add_favorite():
    if g.user is None:
        return jsonify({'error': 'Please log in first'}), 401

    station_number = request.form.get('station_number')
    if not station_number:
        return jsonify({'error': 'Missing station number'}), 400

    user_id = g.user['user_id']
    engine = get_db()

    try:
        with engine.begin() as conn:
            check_query = text("""
                               SELECT favorite_id
                               FROM user_favorites
                               WHERE user_id = :user_id
                                 AND station_number = :station_number
                               """)
            if conn.execute(check_query, {"user_id": user_id, "station_number": station_number}).fetchone():
                return jsonify({'message': 'This station is already in your favorites'}), 200

            insert_query = text("""
                                INSERT INTO user_favorites (user_id, station_number)
                                VALUES (:user_id, :station_number)
                                """)
            conn.execute(insert_query, {"user_id": user_id, "station_number": station_number})

        return jsonify({'message': 'Added to favorites successfully!'}), 201
    except Exception as e:
        return jsonify({'error': 'Operation failed, please ensure the station number is valid', 'details': str(e)}), 400


# 2. Retrieve all favorites for the current user
@auth_bp.route('/favorites', methods=['GET'])
def get_my_favorites():
    if g.user is None:
        return jsonify({'error': 'Please log in first'}), 401

    user_id = g.user['user_id']
    engine = get_db()

    with engine.connect() as conn:
        query = text("""
                     SELECT f.favorite_id, f.station_number, f.added_at
                     FROM user_favorites f
                     WHERE f.user_id = :user_id
                     ORDER BY f.added_at DESC
                     """)
        results = conn.execute(query, {"user_id": user_id}).fetchall()

        favorites = [dict(row.items()) for row in results]

    return jsonify({
        'user_id': user_id,
        'favorites': favorites
    }), 200


# 3. Delete Favorite
@auth_bp.route('/favorites/<int:station_number>', methods=['DELETE'])
def delete_favorite(station_number):
    if g.user is None:
        return jsonify({'error': 'Please log in first'}), 401

    user_id = g.user['user_id']
    engine = get_db()

    with engine.begin() as conn:
        delete_query = text("""
                            DELETE
                            FROM user_favorites
                            WHERE user_id = :user_id
                              AND station_number = :station_number
                            """)
        result = conn.execute(delete_query, {"user_id": user_id, "station_number": station_number})

        if result.rowcount == 0:
            return jsonify({'error': 'Favorite record not found'}), 404

    return jsonify({'message': 'Favorite removed'}), 200






