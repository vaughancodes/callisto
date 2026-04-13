from celery import Celery
from flask import Flask
from flask_cors import CORS

from callisto.config import Config
from callisto.extensions import db


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    CORS(app, origins=[app.config.get("FRONTEND_URL", "http://localhost:5173")],
         supports_credentials=True)

    from callisto.api import bp as api_bp
    from callisto.api.admin import admin_bp
    from callisto.api.webhooks import webhooks_bp
    from callisto.auth.routes import auth_bp

    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(auth_bp)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


def create_celery(app: Flask | None = None) -> Celery:
    if app is None:
        app = create_app()

    celery = Celery(app.import_name)
    celery.config_from_object(app.config["CELERY"])

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
