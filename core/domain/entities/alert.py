from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Alert:
    id: int
    device_id: int
    alert_type: Optional[str] = None    # e.g. 'speeding', 'geofence_exit', 'offline'
    severity: Optional[str] = None      # 'low', 'medium', 'high', 'critical'
    metadata: Optional[dict] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    resolved: bool = False
