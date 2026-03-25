from dataclasses import dataclass
from typing import Optional, Any
from datetime import date, datetime


@dataclass
class DailyRoute:
    id: int
    device_id: int
    route_date: Optional[date] = None
    route_geom: Optional[Any] = None    # PostGIS LineString
    distance_km: Optional[float] = None
    duration_minutes: Optional[int] = None
    created_at: Optional[datetime] = None
