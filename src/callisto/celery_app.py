from callisto.app import create_app, create_celery

flask_app = create_app()
celery = create_celery(flask_app)

# Celery CLI (-A) autodiscovers the `app` attribute — point it at the Celery instance
app = celery

# Import tasks so they are registered with the celery instance
import callisto.tasks  # noqa: E402, F401
