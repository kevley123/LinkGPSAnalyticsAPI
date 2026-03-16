from typing import List, Tuple
from django.db import connection
from core.domain.entities.notification import Notification
from core.domain.ports.notification_repository import NotificationRepository

class NotificationRepositoryImpl(NotificationRepository):
    def get_paginated_by_user_id(self, user_id: int, limit: int, offset: int) -> Tuple[List[Notification], int]:
        with connection.cursor() as cursor:
            # First, get the total count of notifications for the user
            count_query = """
                SELECT COUNT(id) 
                FROM notificaciones_personales
                WHERE receptor_id = %s
            """
            cursor.execute(count_query, [user_id])
            total_count = cursor.fetchone()[0]

            # Then, fetch the paginated results ordered by created_at DESC
            data_query = """
                SELECT id, receptor_id, tipo, titulo, mensaje, leido, created_at
                FROM notificaciones_personales
                WHERE receptor_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(data_query, [user_id, limit, offset])
            rows = cursor.fetchall()

        notifications = [
            Notification(
                id=r[0], 
                receptor_id=r[1], 
                tipo=r[2],
                titulo=r[3], 
                mensaje=r[4], 
                leido=r[5], 
                created_at=r[6]
            )
            for r in rows
        ]

        return notifications, total_count
