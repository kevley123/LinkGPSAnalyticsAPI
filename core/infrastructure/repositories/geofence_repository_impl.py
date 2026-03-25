from typing import List, Optional
from core.domain.entities.geofence import Geofence as GeofenceEntity
from core.domain.ports.geofence_repository import IGeofenceRepository
from core.models import Geofence as GeofenceModel
from django.db import connection


def _to_entity(m: GeofenceModel) -> GeofenceEntity:
    return GeofenceEntity(
        id=m.pk,
        vehicle_id=m.vehicle_id,
        name=m.name,
        geom=m.geom,
        active=m.active,
        type=m.type,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class GeofenceRepositoryImpl(IGeofenceRepository):

    def get_by_vehicle(self, vehicle_id: int) -> List[GeofenceEntity]:
        qs = GeofenceModel.objects.filter(vehicle_id=vehicle_id)
        return [_to_entity(m) for m in qs]

    def get_by_id(self, geofence_id: int) -> Optional[GeofenceEntity]:
        try:
            return _to_entity(GeofenceModel.objects.get(pk=geofence_id))
        except GeofenceModel.DoesNotExist:
            return None

    def check_point_in_geofence(
        self, geofence_id: int, latitude: float, longitude: float
    ) -> bool:
        """Uses PostGIS ST_Contains for spatial containment check."""
        sql = """
            SELECT ST_Contains(
                geom::geometry,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            )
            FROM tracking.geofences
            WHERE id = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [longitude, latitude, geofence_id])
            row = cursor.fetchone()
        return bool(row[0]) if row else False
