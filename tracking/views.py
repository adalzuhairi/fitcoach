from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Profile
from nutrition.models import NutritionPlan
from training.models import Program

from . import services
from .forms import BodyMeasurementForm
from .models import BodyMeasurement


@login_required
def dashboard(request):
    """Tableau de bord : prochaine séance, objectifs du jour, poids, progression."""
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None:
        return redirect("accounts:onboarding")

    program = (
        Program.objects.filter(user=request.user, actif=True)
        .prefetch_related("workout_days__exercises")
        .first()
    )
    plan = NutritionPlan.objects.filter(user=request.user, actif=True).first()

    prochaine = services.prochaine_seance(request.user, program)
    historique = services.historique_poids(request.user)

    return render(
        request,
        "tracking/dashboard.html",
        {
            "profile": profile,
            "program": program,
            "plan": plan,
            "prochaine_seance": prochaine,
            "poids_actuel": services.poids_actuel(request.user, profile),
            "historique_poids": historique,
        },
    )


def _tours_disponibles(serie):
    """(champ, label) des tours qui ont au moins une valeur dans la série."""
    labels = {
        champ: BodyMeasurement._meta.get_field(champ).verbose_name
        for champ in services.CHAMPS_TOURS
    }
    return [
        (champ, labels[champ])
        for champ in services.CHAMPS_TOURS
        if any(point[champ] is not None for point in serie)
    ]


@login_required
def mesures(request):
    """Liste/historique des mesures corporelles + formulaire de saisie rapide."""
    if request.method == "POST":
        form = BodyMeasurementForm(request.POST, request.FILES)
        if form.is_valid():
            services.enregistrer_mesure(request.user, form.cleaned_data)
            messages.success(request, "Mesure enregistrée.")
            return redirect("tracking:mesures")
    else:
        form = BodyMeasurementForm()

    mesures_qs = BodyMeasurement.objects.filter(user=request.user)
    serie = services.historique_mesures(request.user)
    return render(
        request,
        "tracking/mesures.html",
        {
            "form": form,
            "mesures": mesures_qs,
            "historique": serie,
            "tours_disponibles": _tours_disponibles(serie),
        },
    )


@login_required
def modifier_mesure(request, pk):
    """Édition d'une mesure existante (scopée à l'utilisateur)."""
    mesure = get_object_or_404(BodyMeasurement, pk=pk, user=request.user)
    if request.method == "POST":
        form = BodyMeasurementForm(request.POST, request.FILES, instance=mesure)
        if form.is_valid():
            form.save()
            messages.success(request, "Mesure mise à jour.")
            return redirect("tracking:mesures")
    else:
        form = BodyMeasurementForm(instance=mesure)
    return render(
        request,
        "tracking/mesure_form.html",
        {"form": form, "mesure": mesure},
    )


@login_required
@require_POST
def supprimer_mesure(request, pk):
    """Suppression d'une mesure (POST uniquement)."""
    mesure = get_object_or_404(BodyMeasurement, pk=pk, user=request.user)
    mesure.delete()
    messages.success(request, "Mesure supprimée.")
    return redirect("tracking:mesures")


@login_required
def progression(request):
    """Graphiques de progression : charge par exercice + volume hebdomadaire."""
    exercices = services.exercices_logges(request.user)

    selection = None
    if exercices:
        choisi = request.GET.get("exercice")
        selection = next((e for e in exercices if str(e.id) == choisi), exercices[0])

    charge = services.progression_charge(request.user, selection) if selection else []
    volume = services.volume_hebdomadaire(request.user)

    return render(
        request,
        "tracking/progression.html",
        {
            "exercices": exercices,
            "selection": selection,
            "charge": charge,
            "volume": volume,
        },
    )
