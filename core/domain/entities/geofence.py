from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime


@dataclass
class Geofence:
    id: int
    vehicle_id: Optional[int] = None
    name: Optional[str] = None
    geom: Optional[Any] = None          # PostGIS geometry (Polygon/MultiPolygon)
    active: bool = True
    type: Optional[str] = None          # e.g. 'include', 'exclude'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
