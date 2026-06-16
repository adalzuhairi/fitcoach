import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Materiel, Niveau
from tracking.models import SetLog, WorkoutLog

from . import services
from .models import GroupeMusculaire, Program, WorkoutDay, WorkoutExercise


@login_required
def programme(request):
    """Mon programme : vue du split complet, détail de chaque journée."""
    program = (
        Program.objects.filter(user=request.user, actif=True)
        .prefetch_related("workout_days__exercises__exercise")
        .first()
    )
    if program is None:
        messages.info(request, "Aucun programme actif. Complète ton profil pour en générer un.")
        return redirect("accounts:onboarding")
    return render(request, "training/programme.html", {"program": program})


@login_required
def seance(request, workout_day_id):
    """Mode séance (mobile) : saisie reps/charge, chrono de repos, suggestion de charge."""
    workout_day = get_object_or_404(
        WorkoutDay, pk=workout_day_id, program__user=request.user
    )
    log = services.get_or_create_seance_du_jour(request.user, workout_day)

    exercices = []
    for we in workout_day.exercises.select_related("exercise"):
        sets_map = {
            s.serie_numero: s
            for s in SetLog.objects.filter(workout_log=log, workout_exercise=we)
        }
        suggestion = services.suggestion_charge(we, request.user)
        series = []
        for numero in range(1, we.series + 1):
            s = sets_map.get(numero)
            series.append(
                {
                    "numero": numero,
                    "fait": s is not None,
                    "reps": s.repetitions_faites if s else None,
                    "charge": float(s.charge_kg) if s else None,
                }
            )
        ex = we.exercise
        exercices.append(
            {
                "weId": we.id,
                "nom": ex.nom,
                "cible": f"{we.series} × {we.repetitions}",
                "repos": we.temps_repos_secondes,
                "notes": we.notes,
                "suggestion": float(suggestion) if suggestion is not None else None,
                "series": series,
                # Guide débutant « Comment exécuter ? » (encart dépliable, mobile).
                "guide": {
                    "execution": ex.description_technique,
                    "securite": ex.consignes_securite,
                    "erreurs": ex.erreurs_frequentes,
                    "musclePrimaire": ex.get_groupe_musculaire_display(),
                    "musclesSecondaires": ex.muscles_secondaires,
                    "aGuide": bool(
                        ex.description_technique
                        or ex.consignes_securite
                        or ex.erreurs_frequentes
                        or ex.muscles_secondaires
                    ),
                },
            }
        )

    seance_data = {"logId": log.id, "exercices": exercices}
    return render(
        request,
        "training/seance.html",
        {"workout_day": workout_day, "log": log, "seance_data": seance_data},
    )


@login_required
@require_POST
def enregistrer_serie(request):
    """Endpoint JSON : enregistre une série depuis le mode séance (fetch)."""
    try:
        data = json.loads(request.body)
        log = get_object_or_404(WorkoutLog, pk=data["logId"], user=request.user)
        we = get_object_or_404(
            WorkoutExercise,
            pk=data["weId"],
            workout_day__program__user=request.user,
        )
        setlog = services.enregistrer_serie(
            log,
            we,
            serie_numero=int(data["serie"]),
            repetitions_faites=int(data["reps"]),
            charge_kg=data["charge"],
            rpe=data.get("rpe"),
        )
    except (KeyError, ValueError, TypeError):
        return JsonResponse({"ok": False, "erreur": "Données invalides."}, status=400)
    return JsonResponse({"ok": True, "setId": setlog.id})


@login_required
@require_POST
def terminer_seance(request, log_id):
    """Finalise la séance (durée, ressenti, notes) puis retourne au programme."""
    log = get_object_or_404(WorkoutLog, pk=log_id, user=request.user)
    log.duree_minutes = request.POST.get("duree_minutes") or None
    log.ressenti = request.POST.get("ressenti") or None
    log.notes = request.POST.get("notes", "")
    log.save()
    messages.success(request, "Séance enregistrée. Bon boulot 💪")
    return redirect("training:programme")


@login_required
def bibliotheque(request):
    """Bibliothèque d'exercices : recherche plein texte + filtres combinables."""
    query = request.GET.get("q", "").strip()
    groupe = request.GET.get("groupe", "")
    materiel = request.GET.get("materiel", "")
    niveau = request.GET.get("niveau", "")

    exercices = services.rechercher_exercices(
        query=query or None,
        groupe=groupe or None,
        materiel=materiel or None,
        niveau=niveau or None,
    )

    return render(
        request,
        "training/bibliotheque.html",
        {
            "exercices": exercices,
            "query": query,
            "groupe": groupe,
            "materiel": materiel,
            "niveau": niveau,
            "groupes": GroupeMusculaire.choices,
            "materiels": Materiel.choices,
            "niveaux": Niveau.choices,
        },
    )


@login_required
def exercice(request, exercice_id):
    """Fiche technique d'un exercice."""
    obj = services.exercice_detail(exercice_id)
    if obj is None:
        raise Http404("Exercice introuvable.")
    return render(request, "training/exercice.html", {"exercice": obj})
