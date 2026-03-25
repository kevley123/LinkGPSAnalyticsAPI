from abc import ABC, abstractmethod
from typing import List
from core.domain.entities.alert import Alert


class IAlertRepository(ABC):

    @abstractmethod
    def get_by_device(self, device_id: int, limit: int = 50) -> List[Alert]:
        pass

    @abstractmethod
    def get_unresolved(self, device_id: int) -> List[Alert]:
        pass

    @abstractmethod
    def resolve(self, alert_id: int) -> bool:
        pass
