"""URL configuration for config project (FitCoach)."""

from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import include, path


def healthcheck(request):
    """Endpoint de supervision (vérifie que l'app tourne)."""
    return JsonResponse({"status": "ok", "app": "fitcoach"})


@login_required
def home(request):
    """Racine : redirige vers le récap profil (ou l'onboarding si pas de profil)."""
    return redirect("accounts:profil")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthcheck, name="healthcheck"),
    # Auth Django (login/logout/reset) — django-allauth prévu en Phase 3.
    path("", include("django.contrib.auth.urls")),
    path("compte/", include("accounts.urls")),
    path("entrainement/", include("training.urls")),
    path("nutrition/", include("nutrition.urls")),
    path("", home, name="home"),
]
