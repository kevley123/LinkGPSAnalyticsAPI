from django.urls import path
from .views import health
from core.api.controllers.vehicle_controller import get_vehicles_by_user
from core.api.controllers.notification_controller import get_notifications_by_user

urlpatterns = [
    path('health/', health),
    path('vehiculos', get_vehicles_by_user),
    path('notificaciones', get_notifications_by_user),
]
