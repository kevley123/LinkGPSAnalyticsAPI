from rest_framework.decorators import api_view
from rest_framework.response import Response

from application.services.vehicle_service import get_user_vehicles

@api_view(["POST"])
def vehiculos(request):

    user_id = request.data.get("user_id")

    vehicles = get_user_vehicles(user_id)

    return Response({
        "success": True,
        "vehiculos": vehicles
    })