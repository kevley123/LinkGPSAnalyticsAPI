from dataclasses import dataclass
from typing import Optional, Any
from datetime import datetime


@dataclass
class RiskZone:
    id: int
    name: Optional[str] = None
    geom: Optional[Any] = None          # PostGIS Polygon
    risk_level: Optional[float] = None  # 0.0 - 1.0
    source: Optional[str] = None
    confidence: Optional[float] = None
    votes_up: int = 0
    votes_down: int = 0
    reports: int = 0
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
