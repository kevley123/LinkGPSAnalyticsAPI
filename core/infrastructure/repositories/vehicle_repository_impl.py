from typing import List
from django.db import connection
from core.domain.entities.vehicle import Vehicle
from core.domain.ports.vehicle_repository import VehicleRepository

class VehicleRepositoryImpl(VehicleRepository):
    def get_all(self) -> List[Vehicle]:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, placa, modelo, cliente_id FROM vehiculos")
            rows = cursor.fetchall()
        
        return [
            Vehicle(id=r[0], placa=r[1], modelo=r[2], cliente_id=r[3])
            for r in rows
        ]

    def get_by_user_id(self, user_id: int) -> List[Vehicle]:
        # El gateway envía user_id. Buscamos el cliente que tiene ese user_id, 
        # y luego los vehículos que tienen ese cliente_id. Usamos un JOIN.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.placa, v.modelo, v.cliente_id 
                FROM vehiculos v
                INNER JOIN clientes c ON v.cliente_id = c.id
                WHERE c.user_id = %s
                """,
                [user_id]
            )
            rows = cursor.fetchall()
        
        return [
            Vehicle(id=r[0], placa=r[1], modelo=r[2], cliente_id=r[3])
            for r in rows
        ]
