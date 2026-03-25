from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class GeofenceEvent:
    id: int
    geofence_id: int
    device_id: int
    position_id: Optional[int] = None
    event_type: Optional[str] = None    # 'enter', 'exit'
    created_at: Optional[datetime] = None
    metadata: Optional[dict] = field(default_factory=dict)
