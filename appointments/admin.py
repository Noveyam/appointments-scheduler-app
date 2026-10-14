"""Register appointment models with Django admin."""
from django.contrib import admin

from .models import Appointment, Hairdresser, Service

admin.site.register(Service)
admin.site.register(Hairdresser)
admin.site.register(Appointment)
