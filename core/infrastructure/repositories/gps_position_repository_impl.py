from typing import List, Optional
from datetime import datetime
from django.db import connection
from core.domain.entities.gps_position import GpsPosition as GpsPositionEntity
from core.domain.ports.gps_position_repository import IGpsPositionRepository
from core.models import GpsPosition as GpsPositionModel


def _to_entity(m: GpsPositionModel) -> GpsPositionEntity:
    return GpsPositionEntity(
        id=m.pk,
        device_id=m.device_id,
        geom=m.geom,
        speed=m.speed,
        heading=m.heading,
        altitude=m.altitude,
        satellites=m.satellites,
        accuracy=m.accuracy,
        recorded_at=m.recorded_at,
        metadata=m.metadata or {},
    )


class GpsPositionRepositoryImpl(IGpsPositionRepository):

    def get_last_by_device(self, device_id: int) -> Optional[GpsPositionEntity]:
        """Leverages TimescaleDB ordering for efficient last-point query."""
        qs = GpsPositionModel.objects.filter(device_id=device_id).order_by('-recorded_at').first()
        return _to_entity(qs) if qs else None

    def get_range_by_device(
        self, device_id: int, from_dt: datetime, to_dt: datetime
    ) -> List[GpsPositionEntity]:
        qs = GpsPositionModel.objects.filter(
            device_id=device_id,
            recorded_at__gte=from_dt,
            recorded_at__lte=to_dt,
        ).order_by('recorded_at')
        return [_to_entity(m) for m in qs]

    def get_latest_positions(self, limit: int = 100) -> List[GpsPositionEntity]:
        """
        Uses TimescaleDB optimized DISTINCT ON query to get the latest GPS
        position for each device — very fast on the hypertable.
        """
        sql = """
            SELECT DISTINCT ON (device_id)
                id, device_id,
                ST_X(geom::geometry) AS longitude,
                ST_Y(geom::geometry) AS latitude,
                speed, heading, altitude, satellites, accuracy,
                recorded_at, metadata
            FROM tracking.gps_positions
            ORDER BY device_id, recorded_at DESC
            LIMIT %s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [limit])
            rows = cursor.fetchall()

        entities = []
        for row in rows:
            entities.append(GpsPositionEntity(
                id=row[0],
                device_id=row[1],
                geom=None,  # raw lat/lng available below
                speed=row[4],
                heading=row[5],
                altitude=row[6],
                satellites=row[7],
                accuracy=row[8],
                recorded_at=row[9],
                metadata=row[10] or {},
            ))
        return entities
