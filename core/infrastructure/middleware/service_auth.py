from django.http import JsonResponse
from django.conf import settings

class ServiceAuthMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Bypass for health check or if DEBUG is True and no header provided
        if request.path.endswith('/health/') or (settings.DEBUG and not request.headers.get("Authorization")):
            return self.get_response(request)

        auth = request.headers.get("Authorization")
        expected = f"Bearer {settings.ANALYTICS_API_KEY}"

        if auth != expected:
            return JsonResponse({"error": "Unauthorized", "message": "Missing or invalid Authorization header"}, status=401)

        return self.get_response(request)