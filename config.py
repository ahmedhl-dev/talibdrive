import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

def get_database_url():
    url = os.environ.get("DATABASE_URL")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url or "sqlite:///" + os.path.join(basedir, "talibdrive.db")

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-dev-key-change-me")
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@talibdrive.com")
    SENDER_NAME = os.environ.get("SENDER_NAME", "TalibDrive")
