from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)
    login_manager.login_view = "auth.login"

    from app.routes.auth import auth
    from app.routes.trajets import trajets
    from app.routes.reservations import reservations
    from app.routes.admin import admin

    app.register_blueprint(auth)
    app.register_blueprint(trajets)
    app.register_blueprint(reservations)
    app.register_blueprint(admin)

    with app.app_context():
        from app import models
        db.create_all()

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    return app