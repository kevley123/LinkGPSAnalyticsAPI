from django.urls import path
from .views import health
from core.api.vehicle_controller import get_vehicles

urlpatterns = [
    path('health/', health),
    path('vehicles/', get_vehicles),
]
