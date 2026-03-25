from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime


@dataclass
class TrackedDevice:
    id: int
    device_imei: str
    vehicle_id: Optional[int] = None
    status: Optional[str] = None        # e.g. 'active', 'inactive'
    activated_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    metadata: Optional[dict] = field(default_factory=dict)
    modo: int = 0                       # Operation mode: 0=normal, 1=tracking, 2=block, 3=safe_geofence
