from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.models import Profile

from . import services


@login_required
def complements(request):
    """Compléments conseillés selon l'objectif et les préférences alimentaires du profil."""
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None:
        messages.info(request, "Complète ton profil pour voir des compléments adaptés.")
        return redirect("accounts:onboarding")

    return render(
        request,
        "supplements/complements.html",
        {
            "profile": profile,
            "objectif_label": profile.get_objectif_display(),
            "recommandations": services.recommander_complements(profile),
        },
    )
