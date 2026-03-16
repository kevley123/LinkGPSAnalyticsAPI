from abc import ABC, abstractmethod
from typing import List, Tuple
from core.domain.entities.notification import Notification

class NotificationRepository(ABC):
    @abstractmethod
    def get_paginated_by_user_id(self, user_id: int, limit: int, offset: int) -> Tuple[List[Notification], int]:
        """
        Returns a tuple containing:
        - List of Notification objects for the current page
        - Total count of notifications for the user
        """
        pass
