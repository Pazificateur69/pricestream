from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token


def healthcheck(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.pricing.urls")),
    path("api/auth/token/", obtain_auth_token, name="api-token"),
    path("health/", healthcheck, name="health"),
]
