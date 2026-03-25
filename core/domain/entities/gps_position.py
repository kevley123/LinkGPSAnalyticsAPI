from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime


@dataclass
class GpsPosition:
    """
    Core telemetry entity. Maps to the TimescaleDB hypertable gps_positions.
    Partitioned by recorded_at.
    """
    id: int
    device_id: int
    recorded_at: datetime
    geom: Optional[Any] = None          # PostGIS geometry (Point, SRID 4326)
    speed: Optional[float] = None       # km/h
    heading: Optional[float] = None     # degrees 0-360
    altitude: Optional[float] = None    # meters
    satellites: Optional[int] = None
    accuracy: Optional[float] = None    # meters
    metadata: Optional[dict] = field(default_factory=dict)
