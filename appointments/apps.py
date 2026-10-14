"""Django application configuration."""
from django.apps import AppConfig


class AppointmentsConfig(AppConfig):
    """Configure the appointments app."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "appointments"
