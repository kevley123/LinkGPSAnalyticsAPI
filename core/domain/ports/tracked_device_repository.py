from abc import ABC, abstractmethod
from typing import List, Optional
from core.domain.entities.tracked_device import TrackedDevice


class ITrackedDeviceRepository(ABC):

    @abstractmethod
    def get_by_id(self, device_id: int) -> Optional[TrackedDevice]:
        pass

    @abstractmethod
    def get_by_imei(self, imei: str) -> Optional[TrackedDevice]:
        pass

    @abstractmethod
    def list_all(self) -> List[TrackedDevice]:
        pass

    @abstractmethod
    def update_modo(self, device_id: int, modo: int) -> bool:
        pass
