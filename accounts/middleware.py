"""Middleware d'accès : onboarding obligatoire avant toute autre page."""

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .models import Profile


class OnboardingRequiredMiddleware:
    """Force tout utilisateur connecté sans profil à compléter l'onboarding.

    Tant que le Profile n'existe pas, l'app ne peut proposer ni programme ni
    plan nutritionnel adaptés : on bloque donc l'accès aux pages de contenu et
    on renvoie vers l'onboarding. Les chemins techniques (authentification,
    admin, fichiers statiques, supervision) restent accessibles pour ne pas
    casser la connexion / déconnexion.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Préfixes toujours autorisés, calculés une fois au démarrage.
        self.chemins_libres = tuple(
            self._normaliser(p)
            for p in (
                reverse("accounts:onboarding"),
                "/accounts/",  # django-allauth : login, logout, signup, reset
                "/admin/",
                "/healthz/",
                settings.STATIC_URL,
                settings.MEDIA_URL,
            )
            if p
        )

    def __call__(self, request):
        if self._doit_rediriger(request):
            return redirect("accounts:onboarding")
        return self.get_response(request)

    @staticmethod
    def _normaliser(url: str) -> str:
        """Garantit un préfixe absolu (STATIC_URL vaut « static/ » sans / initial)."""
        return url if url.startswith("/") else "/" + url

    def _doit_rediriger(self, request) -> bool:
        if not request.user.is_authenticated:
            return False
        if request.path.startswith(self.chemins_libres):
            return False
        # Profil présent -> onboarding terminé, accès normal.
        return not Profile.objects.filter(user=request.user).exists()
