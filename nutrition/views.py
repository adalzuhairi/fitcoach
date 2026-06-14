from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.models import Profile

from . import services
from .models import NutritionPlan


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
