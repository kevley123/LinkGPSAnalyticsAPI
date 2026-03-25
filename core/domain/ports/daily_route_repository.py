from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from core.domain.entities.daily_route import DailyRoute


class IDailyRouteRepository(ABC):

    @abstractmethod
    def get_by_device_date(
        self, device_id: int, route_date: date
    ) -> Optional[DailyRoute]:
        pass

    @abstractmethod
    def get_by_device(self, device_id: int, limit: int = 30) -> List[DailyRoute]:
        pass
