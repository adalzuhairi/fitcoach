"""URL configuration for config project (FitCoach)."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import include, path


def healthcheck(request):
    """Endpoint de supervision (vérifie que l'app tourne)."""
    return JsonResponse({"status": "ok", "app": "fitcoach"})


def racine(request):
    """Racine publique : landing pour les visiteurs, dashboard si connecté."""
    if request.user.is_authenticated:
        return redirect("tracking:dashboard")
    return render(request, "landing.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthcheck, name="healthcheck"),
    # Auth multi-utilisateurs : login / signup / reset password (django-allauth).
    path("accounts/", include("allauth.urls")),
    # Landing publique avant l'include tracking (qui réserve les autres chemins).
    path("", racine, name="landing"),
    path("compte/", include("accounts.urls")),
    path("entrainement/", include("training.urls")),
    path("nutrition/", include("nutrition.urls")),
    # tracking : /dashboard/, /mesures/, /progression/.
    path("", include("tracking.urls")),
]

# Sert les fichiers médias (photos de progression) en développement.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
