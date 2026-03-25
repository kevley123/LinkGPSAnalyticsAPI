from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from core.domain.entities.gps_position import GpsPosition


class IGpsPositionRepository(ABC):

    @abstractmethod
    def get_last_by_device(self, device_id: int) -> Optional[GpsPosition]:
        pass

    @abstractmethod
    def get_range_by_device(
        self, device_id: int, from_dt: datetime, to_dt: datetime
    ) -> List[GpsPosition]:
        pass

    @abstractmethod
    def get_latest_positions(self, limit: int = 100) -> List[GpsPosition]:
        """Get the latest position for each active device."""
        pass
