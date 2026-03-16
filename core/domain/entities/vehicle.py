from dataclasses import dataclass
from typing import Optional

@dataclass
class Vehicle:
    id: int
    placa: str
    modelo: str
    cliente_id: int
