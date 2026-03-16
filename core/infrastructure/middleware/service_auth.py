from django.http import JsonResponse
from django.conf import settings

class ServiceAuthMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        auth = request.headers.get("Authorization")

        expected = f"Bearer {settings.ANALYTICS_API_KEY}"

        if auth != expected:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        return self.get_response(request)