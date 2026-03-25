from abc import ABC, abstractmethod
from typing import Optional
from core.domain.entities.device_status import DeviceStatus


class IDeviceStatusRepository(ABC):

    @abstractmethod
    def get_by_device_id(self, device_id: int) -> Optional[DeviceStatus]:
        pass

    @abstractmethod
    def update(self, status: DeviceStatus) -> bool:
        pass
