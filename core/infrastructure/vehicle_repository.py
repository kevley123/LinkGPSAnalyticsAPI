from django.db import connection

class VehicleRepository:

    def get_all(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, placa, modelo, cliente_id FROM vehiculos")
            rows = cursor.fetchall()

        vehicles = []
        for r in rows:
            vehicles.append({
                "id": r[0],
                "placa": r[1],
                "modelo": r[2],
                "cliente_id": r[3]
            })

        return vehicles