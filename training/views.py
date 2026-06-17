import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Materiel, Niveau, Profile
from tracking.models import SetLog, WorkoutLog

from . import services
from .models import Exercise, GroupeMusculaire, Program, WorkoutDay, WorkoutExercise


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


def _bloc_exercice(we, user, log, substitution=None):
    """Construit le dict d'un exercice pour le mode séance (réutilisé par les
    endpoints de substitution).

    `substitution` : instance SubstitutionSeance active sur ce créneau, ou None.
    Quand un substitut est actif, le nom / guide / suggestion portent sur le
    substitut, mais les séries restent rattachées au créneau (`we`).
    """
    exo = substitution.exercise_substitut if substitution else we.exercise
    substitut = substitution.exercise_substitut if substitution else None

    sets_map = {
        s.serie_numero: s
        for s in SetLog.objects.filter(workout_log=log, workout_exercise=we)
    }
    suggestion = services.suggestion_charge(we, user, exercise_substitut=substitut)
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
    return {
        "weId": we.id,
        "nom": exo.nom,
        "cible": f"{we.series} × {we.repetitions}",
        "repos": we.temps_repos_secondes,
        "notes": we.notes,
        "suggestion": float(suggestion) if suggestion is not None else None,
        "series": series,
        # Badge « remplacé » : nom de l'exercice du programme mis de côté ce jour.
        "substitution": ({"original": we.exercise.nom} if substitution else None),
        # Guide débutant « Comment exécuter ? » (encart dépliable, mobile).
        "guide": {
            "execution": exo.description_technique,
            "securite": exo.consignes_securite,
            "erreurs": exo.erreurs_frequentes,
            "musclePrimaire": exo.get_groupe_musculaire_display(),
            "musclesSecondaires": exo.muscles_secondaires,
            "aGuide": bool(
                exo.description_technique
                or exo.consignes_securite
                or exo.erreurs_frequentes
                or exo.muscles_secondaires
            ),
        },
    }


@login_required
def seance(request, workout_day_id):
    """Mode séance (mobile) : saisie reps/charge, chrono de repos, suggestion de charge."""
    workout_day = get_object_or_404(
        WorkoutDay, pk=workout_day_id, program__user=request.user
    )
    log = services.get_or_create_seance_du_jour(request.user, workout_day)

    subs = {
        s.workout_exercise_id: s
        for s in log.substitutions.select_related("exercise_substitut")
    }
    exercices = [
        _bloc_exercice(we, request.user, log, substitution=subs.get(we.id))
        for we in workout_day.exercises.select_related("exercise")
    ]

    seance_data = {"logId": log.id, "exercices": exercices}
    return render(
        request,
        "training/seance.html",
        {"workout_day": workout_day, "log": log, "seance_data": seance_data},
    )


@login_required
def alternatives_exercice(request, we_id):
    """JSON : alternatives proposées pour remplacer un exercice de la séance.

    Scopé à l'utilisateur (le créneau doit appartenir à un de SES programmes).
    """
    we = get_object_or_404(
        WorkoutExercise, pk=we_id, workout_day__program__user=request.user
    )
    profile = Profile.objects.filter(user=request.user).first()
    alternatives = [
        {
            "id": a["exercise"].id,
            "nom": a["exercise"].nom,
            "groupe": a["exercise"].get_groupe_musculaire_display(),
            "type": a["exercise"].get_type_display(),
            "materiel": a["exercise"].get_materiel_requis_display(),
            "materielDifferent": a["materiel_different"],
        }
        for a in services.alternatives_exercice(we, profile)
    ]
    return JsonResponse({"alternatives": alternatives})


def _charger_log_et_we(request, data):
    """Récupère (log, we) scopés à l'utilisateur et cohérents entre eux.

    Lève Http404 si l'un n'appartient pas à l'utilisateur ; renvoie (None, None)
    si le créneau n'est pas celui de la journée du log (incohérence → 400 côté
    appelant).
    """
    log = get_object_or_404(WorkoutLog, pk=data["logId"], user=request.user)
    we = get_object_or_404(
        WorkoutExercise, pk=data["weId"], workout_day__program__user=request.user
    )
    if we.workout_day_id != log.workout_day_id:
        return None, None
    return log, we


@login_required
@require_POST
def substituer(request):
    """Endpoint JSON : remplace un exercice pour la séance du jour (option B).

    Vérifie que l'exercice cible est une alternative LÉGITIME (recalculée côté
    serveur) — on n'accepte pas n'importe quel exercise_id envoyé en POST.
    Renvoie le bloc d'exercice rafraîchi (substitut) pour swap en place.
    """
    try:
        data = json.loads(request.body)
        log, we = _charger_log_et_we(request, data)
        if log is None:
            return JsonResponse({"ok": False, "erreur": "Créneau incohérent."}, status=400)
        exercise_id = int(data["exerciseId"])
    except (KeyError, ValueError, TypeError):
        return JsonResponse({"ok": False, "erreur": "Données invalides."}, status=400)

    profile = Profile.objects.filter(user=request.user).first()
    ids_legitimes = {
        a["exercise"].id for a in services.alternatives_exercice(we, profile)
    }
    if exercise_id not in ids_legitimes:
        return JsonResponse(
            {"ok": False, "erreur": "Alternative non autorisée."}, status=400
        )

    substitut = Exercise.objects.get(pk=exercise_id)
    from tracking import services as tracking_services

    sub = tracking_services.substituer_exercice(log, we, substitut)
    return JsonResponse(
        {"ok": True, "exercice": _bloc_exercice(we, request.user, log, substitution=sub)}
    )


@login_required
@require_POST
def annuler_substitution(request):
    """Endpoint JSON : annule la substitution du jour (undo) et repart du programme."""
    try:
        data = json.loads(request.body)
        log, we = _charger_log_et_we(request, data)
        if log is None:
            return JsonResponse({"ok": False, "erreur": "Créneau incohérent."}, status=400)
    except (KeyError, ValueError, TypeError):
        return JsonResponse({"ok": False, "erreur": "Données invalides."}, status=400)

    from tracking import services as tracking_services

    tracking_services.annuler_substitution(log, we)
    return JsonResponse(
        {"ok": True, "exercice": _bloc_exercice(we, request.user, log, substitution=None)}
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
