from typing import Dict, Any
from core.domain.ports.notification_repository import NotificationRepository

class GetUserNotifications:
    def __init__(self, repository: NotificationRepository):
        self.repository = repository

    def execute(self, user_id: int, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        """
        Retrieves paginated notifications for a given user.
        Calculates offset based on page and limit.
        """
        # Ensure page is at least 1
        page = max(1, page)
        offset = (page - 1) * limit
        
        notifications, total_count = self.repository.get_paginated_by_user_id(
            user_id=user_id, 
            limit=limit, 
            offset=offset
        )
        
        # Calculate total pages
        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0
        
        # Convert domain entities to dictionaries for the API response
        notification_list = [
            {
                "id": n.id,
                "receptor_id": n.receptor_id,
                "tipo": n.tipo,
                "titulo": n.titulo,
                "mensaje": n.mensaje,
                "leido": n.leido,
                "created_at": n.created_at.isoformat() if n.created_at else None
            }
            for n in notifications
        ]
        
        return {
            "data": notification_list,
            "meta": {
                "current_page": page,
                "per_page": limit,
                "total_items": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            }
        }
