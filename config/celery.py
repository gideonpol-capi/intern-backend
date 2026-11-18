import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
# Every setting starting with CELERY_ in settings.py configures Celery.
app.config_from_object("django.conf:settings", namespace="CELERY")
# Finds tasks.py in every installed app.
app.autodiscover_tasks()


@app.task
def ping():
    """Smoke test: `docker compose exec web python manage.py shell -c "from config.celery import ping; print(ping.delay().get(timeout=10))"`"""
    return "pong"
