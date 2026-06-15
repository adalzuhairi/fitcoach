from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import JsonResponse

from coach import services as coach_services
from nutrition import services
from nutrition.models import NutritionPlan

from .forms import ProfileForm
from .models import Profile


@login_required
def onboarding(request):
    """Formulaire multi-étapes (rendu en une page, navigation via Alpine.js).

    À la validation : enregistre le Profile, calcule TDEE/macros et crée le
    plan nutritionnel actif (cf. nutrition.services). La logique métier reste
    dans les services, pas dans la vue.
    """
    profile = Profile.objects.filter(user=request.user).first()

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            services.creer_plan_nutritionnel(
                request.user, profile, form.cleaned_data["nombre_repas"]
            )
            # Génère le premier programme d'entraînement (IA, avec fallback templates).
            coach_services.generate_program(profile)
            messages.success(
                request, "Profil enregistré, ton plan et ton programme sont prêts."
            )
            return redirect("accounts:profil")
    else:
        plan = NutritionPlan.objects.filter(user=request.user, actif=True).first()
        initial = {"nombre_repas": plan.nombre_repas} if plan else {}
        form = ProfileForm(instance=profile, initial=initial)

    return render(request, "accounts/onboarding.html", {"form": form})


@login_required
def profil(request):
    """Récapitulatif : profil + plan nutritionnel actif (calories, macros, repas)."""
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None:
        return redirect("accounts:onboarding")

    plan = (
        NutritionPlan.objects.filter(user=request.user, actif=True)
        .prefetch_related("meals")
        .first()
    )
    return render(request, "accounts/profil.html", {"profile": profile, "plan": plan})


@login_required
def tutoriel_seen(request):
    """Marque le tutoriel comme vu côté serveur (POST).

    Utilisé pour la persistance multi-appareil (P2). Retourne JSON.
    """
    if request.method == "POST":
        profile = Profile.objects.filter(user=request.user).first()
        if profile:
            profile.tutoriel_vu = True
            profile.save(update_fields=["tutoriel_vu"])
            return JsonResponse({"ok": True})
    return JsonResponse({"ok": False}, status=400)
