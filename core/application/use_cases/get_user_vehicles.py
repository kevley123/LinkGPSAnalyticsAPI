from typing import List, Dict
from core.domain.ports.vehicle_repository import VehicleRepository

class GetUserVehicles:
    def __init__(self, repository: VehicleRepository):
        self.repository = repository

    def execute(self, user_id: int) -> List[Dict]:
        vehicles = self.repository.get_by_user_id(user_id)
        # Convert entities to dictionaries for the API response
        return [
            {
                "id": v.id,
                "placa": v.placa,
                "modelo": v.modelo,
                "cliente_id": v.cliente_id
            }
            for v in vehicles
        ]
