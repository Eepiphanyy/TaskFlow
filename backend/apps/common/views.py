from django.http import JsonResponse
from django.utils import timezone

def health_check(request):
    return JsonResponse({
        "code": 200,
        "message": "TaskFlow API is running",
        "data": {
            "service": "taskflow-backend",
            "status": "ok",
            "timestamp": timezone.now().isoformat(),
        },
    })
