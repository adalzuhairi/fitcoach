from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Profile
from coach import services as coach_services

from . import services
from .models import Meal, NutritionPlan, Recipe


@login_required
def ma_nutrition(request):
    """Ma nutrition : calories/macros cibles, répartition par repas, recettes suggérées."""
    plan = (
        NutritionPlan.objects.filter(user=request.user, actif=True)
        .prefetch_related("meals")
        .first()
    )
    if plan is None:
        messages.info(
            request, "Aucun plan nutritionnel actif. Complète ton profil pour en générer un."
        )
        return redirect("accounts:onboarding")

    profile = Profile.objects.filter(user=request.user).first()
    recettes = services.recettes_suggerees(profile) if profile else []

    # Part calorique de chaque macro (protéines/glucides à 4 kcal/g, lipides à 9).
    cal_prot = plan.proteines_g * services.KCAL_PAR_G_PROTEINE
    cal_gluc = plan.glucides_g * services.KCAL_PAR_G_GLUCIDE
    cal_lip = plan.lipides_g * services.KCAL_PAR_G_LIPIDE
    total = cal_prot + cal_gluc + cal_lip or 1
    macros = [
        {"nom": "Protéines", "grammes": plan.proteines_g, "pct": round(cal_prot * 100 / total), "couleur": "bg-accent"},
        {"nom": "Glucides", "grammes": plan.glucides_g, "pct": round(cal_gluc * 100 / total), "couleur": "bg-emerald-500"},
        {"nom": "Lipides", "grammes": plan.lipides_g, "pct": round(cal_lip * 100 / total), "couleur": "bg-amber-500"},
    ]

    return render(
        request,
        "nutrition/nutrition.html",
        {"plan": plan, "recettes": recettes, "macros": macros},
    )


@login_required
def recettes_repas(request, meal_id):
    """Recettes pour un repas : affiche le catalogue IA, génère à la demande (POST)."""
    meal = get_object_or_404(Meal, pk=meal_id, plan__user=request.user)
    # Recettes privées de l'utilisateur (IA ou repli) ; le badge « IA » distingue la source.
    recettes = Recipe.objects.filter(user=request.user).order_by("-cree_le")[:12]
    return render(
        request,
        "nutrition/recettes.html",
        {"meal": meal, "recettes": recettes},
    )


@login_required
@require_POST
def generer_recettes(request, meal_id):
    """Déclenche la génération IA de recettes pour un repas (avec fallback)."""
    meal = get_object_or_404(Meal, pk=meal_id, plan__user=request.user)
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None:
        return redirect("accounts:onboarding")

    recettes = coach_services.generate_recipes(profile, meal, n=3)
    messages.success(request, f"{len(recettes)} recette(s) générée(s) pour « {meal.nom} ».")
    return redirect("nutrition:recettes_repas", meal_id=meal.id)
