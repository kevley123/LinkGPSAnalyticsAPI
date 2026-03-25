from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class DeviceStatus:
    device_id: int
    ignition: Optional[bool] = None
    battery_level: Optional[float] = None
    gsm_signal: Optional[int] = None
    gps_fix: Optional[bool] = None
    last_connection: Optional[datetime] = None
    metadata: Optional[dict] = field(default_factory=dict)
