from core.infrastructure.vehicle_repository import VehicleRepository

class VehicleService:

    def __init__(self):
        self.repo = VehicleRepository()

    def list_vehicles(self):
        return self.repo.get_all()