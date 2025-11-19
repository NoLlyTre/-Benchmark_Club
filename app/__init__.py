import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask

from config import load_config
from .achievements import sync_achievements_catalog
from .extensions import csrf, db, login_manager, migrate
from .routes import register_blueprints


def create_app(config_class=None):
    """Application factory."""
    app = Flask(__name__, instance_relative_config=True)
    config_cls = config_class or load_config()
    app.config.from_object(config_cls)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    _configure_logging(app)
    _register_extensions(app)
    _register_context_processors(app)
    _register_blueprints(app)
    _setup_database(app)

    return app


def _configure_logging(app: Flask) -> None:
    """Set up rotating file handler for app logging."""
    log_path = Path(app.config["LOG_PATH"])
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    log_level_name = str(app.config["LOG_LEVEL"]).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    for handler in list(app.logger.handlers):
        app.logger.removeHandler(handler)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    app.logger.info("Logging configured at %s level", log_level_name)


def _register_extensions(app: Flask) -> None:
    """Bind Flask extensions to the application."""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)


def _register_blueprints(app: Flask) -> None:
    """Register application blueprints."""
    register_blueprints(app)


def _register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        from flask_wtf.csrf import generate_csrf
        from markupsafe import Markup
        
        def csrf_token():
            token = generate_csrf()
            return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')
        
        return {
            "current_year": datetime.utcnow().year,
            "csrf_token": csrf_token,
        }


def _setup_database(app: Flask) -> None:
    with app.app_context():
        db.create_all()
        sync_achievements_catalog()
        upload_root = Path(app.config["UPLOAD_FOLDER"])
        for subdir in (
            app.config["BUILD_IMAGE_SUBDIR"],
            app.config["BENCHMARK_IMAGE_SUBDIR"],
        ):
            (upload_root / subdir).mkdir(parents=True, exist_ok=True)
