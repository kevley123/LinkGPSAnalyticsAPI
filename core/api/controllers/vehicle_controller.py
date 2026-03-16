from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.application.use_cases.get_user_vehicles import GetUserVehicles
from core.infrastructure.repositories.vehicle_repository_impl import VehicleRepositoryImpl

@api_view(['POST'])
def get_vehicles_by_user(request):
    user_id = request.data.get("user_id")

    if not user_id:
        return Response({"success": False, "message": "user_id is required"}, status=400)

    try:
        repo = VehicleRepositoryImpl()
        use_case = GetUserVehicles(repo)
        vehicles = use_case.execute(user_id)

        return Response({
            "success": True,
            "vehiculos": vehicles
        })
    except Exception as e:
        return Response({
            "success": False,
            "message": str(e)
        }, status=500)
