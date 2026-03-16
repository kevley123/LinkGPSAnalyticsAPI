from infrastructure.repositories.vehicle_repository import VehicleRepository

def get_user_vehicles(user_id):

    repo = VehicleRepository()

    vehicles = repo.get_by_user(user_id)

    return vehicles