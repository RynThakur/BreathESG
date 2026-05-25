from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.middleware.csrf import get_token


def health(request):
    return JsonResponse({'status': 'ok', 'service': 'breathe-esg-api'})


def csrf(request):
    return JsonResponse({'csrfToken': get_token(request)})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health),
    path('api/csrf/', csrf),
    path('api/', include('ingestion.urls')),
]