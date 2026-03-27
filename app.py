from flask import Flask
from flask_cors import CORS

from config import Config
from db import close_db
from routes_auth import auth_bp
from routes_admin import admins_bp
from routes_questions import questions_bp
from routes_activity import activity_bp
from routes_counters import counters_bp
from dotenv import load_dotenv
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(auth_bp,       url_prefix="/api/auth")
    app.register_blueprint(admins_bp,     url_prefix="/api/admins")
    app.register_blueprint(questions_bp,  url_prefix="/api/questions")
    app.register_blueprint(activity_bp,   url_prefix="/api/activity")
    app.register_blueprint(counters_bp,   url_prefix="/api/counters")

    app.teardown_appcontext(close_db)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run()