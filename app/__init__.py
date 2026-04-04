"""
This file should ONLY contain "create_app" function
"""
from flask import Flask
from flask_cors import CORS

## from my_project.app.main import cache
## from my_project.app.main.routes import live_bp, db_bp
# from my_project.app.main.get_currrent_data_return_json import live_bp, cache
# from my_project.app.main.connection_to_db_return_json import db_bp
from config import Config
from datetime import timedelta
from .routes.machine_learning import ml_bp


def create_app(config_class=Config):
    ## app = Flask(__name__, static_url_path='')
    app = Flask(__name__)


    # Import blueprints and cache AFTER creating app but BEFORE using them
    from .routes.main import main_bp, cache
    from .routes.auth import auth_bp

    app.config.from_object(config_class)
    CORS(app, resources={r"/*": {"origins": ["http://127.0.0.1:63342", "http://localhost:63342"]}},
         supports_credentials=True)


    # cache
    cache.init_app(app, config={'CACHE_TYPE': 'SimpleCache'})

    app.secret_key = 'your_super_secret_key'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

    app.config.from_object(config_class)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    # http://127.0.0.1:5000/auth/login

    app.register_blueprint(ml_bp, url_prefix='/predict')

    return app
