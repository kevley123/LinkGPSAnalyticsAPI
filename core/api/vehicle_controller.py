from rest_framework.decorators import api_view
from rest_framework.response import Response
from core.application.vehicle_service import VehicleService

@api_view(['GET'])
def get_vehicles(request):

    service = VehicleService()
    vehicles = service.list_vehicles()

    return Response(vehicles)