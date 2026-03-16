from infrastructure.models import Vehiculo

class VehicleRepository:

    def get_by_user(self, user_id):

        vehiculos = Vehiculo.objects.filter(cliente__user_id=user_id)

        return [
            {
                "id": v.id,
                "placa": v.placa,
                "modelo": v.modelo
            }
            for v in vehiculos
        ]