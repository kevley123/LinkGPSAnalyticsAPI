from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.application.use_cases.get_user_notifications import GetUserNotifications
from core.infrastructure.repositories.notification_repository_impl import NotificationRepositoryImpl

@api_view(['POST'])
def get_notifications_by_user(request):
    user_id = request.data.get("user_id")
    # API allows optional page param, defaulting to 1
    page = request.data.get("page", 1)
    
    # API allows optional limit param, defaulting to 10
    limit = request.data.get("limit", 10)

    if not user_id:
        return Response({"success": False, "message": "user_id is required"}, status=400)

    try:
        # We ensure page and limit parameters are integers
        page = int(page)
        limit = int(limit)
        
        repo = NotificationRepositoryImpl()
        use_case = GetUserNotifications(repo)
        
        # execute handles offset mapping and pagination response formatting
        result = use_case.execute(user_id=user_id, page=page, limit=limit)

        return Response({
            "success": True,
            "notificaciones": result["data"],
            "meta": result["meta"]
        })
    except ValueError:
        return Response({
            "success": False,
            "message": "page and limit must be valid integers"
        }, status=400)
    except Exception as e:
        return Response({
            "success": False,
            "message": str(e)
        }, status=500)
