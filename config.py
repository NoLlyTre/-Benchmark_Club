import os
from pathlib import Path


class Config:
    """Base configuration for the Benchmark Club application."""

    BASE_DIR = Path(__file__).resolve().parent
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-super-secret-key")
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or f"sqlite:///{BASE_DIR / 'instance' / 'benchmark_club.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECURITY_PASSWORD_SALT = os.environ.get("SECURITY_PASSWORD_SALT", "phone-salt")
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_NAME = "benchmark_club_session"
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 30  # 30 days

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_PATH = os.environ.get(
        "LOG_PATH",
        str(BASE_DIR / "instance" / "benchmark_club.log"),
    )
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER",
        str(BASE_DIR / "instance" / "uploads"),
    )
    BUILD_IMAGE_SUBDIR = "builds"
    BENCHMARK_IMAGE_SUBDIR = "benchmarks"
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB per upload


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def load_config():
    """Determine which configuration to use."""
    config_name = os.environ.get("FLASK_ENV", "development")
    return config_map.get(config_name, Config)
