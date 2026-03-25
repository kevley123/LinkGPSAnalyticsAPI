from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class DeviceEvent:
    id: int
    device_id: int
    event_type: Optional[str] = None    # e.g. 'ignition_on', 'ignition_off', 'bloqueo'
    position_id: Optional[int] = None
    created_at: Optional[datetime] = None
    metadata: Optional[dict] = field(default_factory=dict)
