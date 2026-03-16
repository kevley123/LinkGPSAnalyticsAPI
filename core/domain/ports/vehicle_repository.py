from abc import ABC, abstractmethod
from typing import List, Optional
from core.domain.entities.vehicle import Vehicle

class VehicleRepository(ABC):
    @abstractmethod
    def get_all(self) -> List[Vehicle]:
        pass

    @abstractmethod
    def get_by_user_id(self, user_id: int) -> List[Vehicle]:
        pass
