from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Notification:
    id: int
    receptor_id: int
    tipo: str
    titulo: str
    mensaje: str
    leido: bool
    created_at: datetime
