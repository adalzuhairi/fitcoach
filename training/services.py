"""Logique métier de l'app training (séances, progression).

Suggestion de charge basée sur la double progression (cf. CLAUDE.md) :
si toutes les séries de la dernière séance ont atteint le haut de la fourchette
de répétitions → +2,5 kg (haut du corps) ou +5 kg (bas du corps).
"""

from __future__ import annotations

import datetime
import re
from decimal import Decimal

from django.db.models import Q

from .models import Exercise, GroupeMusculaire, ProgressionType, WorkoutExercise

# Groupes considérés comme "bas du corps" pour l'incrément de charge.
GROUPES_BAS_DU_CORPS = {GroupeMusculaire.JAMBES, GroupeMusculaire.MOLLETS}

INCREMENT_HAUT = Decimal("2.5")
INCREMENT_BAS = Decimal("5")


def rechercher_exercices(query=None, groupe=None, materiel=None, niveau=None):
    """Recherche filtrée dans la bibliothèque d'exercices (filtres combinables).

    - `query` : recherche insensible à la casse sur le nom (FR et EN) ;
    - `groupe` / `materiel` / `niveau` : filtres exacts (valeurs des TextChoices).
    Tri par groupe musculaire puis nom. Renvoie un QuerySet (paresseux).
    """
    qs = Exercise.objects.all()
    if query:
        qs = qs.filter(Q(nom__icontains=query) | Q(nom_en__icontains=query))
    if groupe:
        qs = qs.filter(groupe_musculaire=groupe)
    if materiel:
        qs = qs.filter(materiel_requis=materiel)
    if niveau:
        qs = qs.filter(niveau_minimum=niveau)
    return qs.order_by("groupe_musculaire", "nom")


def exercice_detail(exercice_id):
    """Fiche complète d'un exercice par son id. Renvoie None si introuvable."""
    return Exercise.objects.filter(pk=exercice_id).first()


def reps_max(repetitions: str) -> int | None:
    """Extrait le haut de la fourchette de répétitions ("8-12" → 12, "10" → 10)."""
    nombres = [int(n) for n in re.findall(r"\d+", repetitions or "")]
    return max(nombres) if nombres else None


def increment_charge(groupe_musculaire: str) -> Decimal:
    """Incrément de charge selon le groupe musculaire (bas vs haut du corps)."""
    return INCREMENT_BAS if groupe_musculaire in GROUPES_BAS_DU_CORPS else INCREMENT_HAUT


def suggestion_charge(workout_exercise: WorkoutExercise, user) -> Decimal | None:
    """Charge suggérée pour le prochain passage, d'après la dernière séance loggée.

    Renvoie None si aucun historique. Applique la double progression :
    si toutes les séries de la dernière séance ont atteint le haut de la fourchette,
    on ajoute l'incrément ; sinon on reprend la charge max de la dernière séance.
    """
    # Import local pour éviter une dépendance circulaire training <-> tracking.
    from tracking.models import SetLog

    derniers = list(
        SetLog.objects.filter(
            workout_exercise=workout_exercise, workout_log__user=user
        ).select_related("workout_log")
    )
    if not derniers:
        return None

    derniere_date = max(s.workout_log.date for s in derniers)
    sets_dernier = [s for s in derniers if s.workout_log.date == derniere_date]
    charge_max = max(s.charge_kg for s in sets_dernier)

    top = reps_max(workout_exercise.repetitions)
    progression_ok = (
        workout_exercise.progression_type == ProgressionType.DOUBLE_PROGRESSION
        and top is not None
        and all(s.repetitions_faites >= top for s in sets_dernier)
    )
    if progression_ok:
        return charge_max + increment_charge(workout_exercise.exercise.groupe_musculaire)
    return charge_max


def get_or_create_seance_du_jour(user, workout_day, jour=None):
    """Récupère (ou crée) la séance loggée du jour pour cette journée d'entraînement."""
    from tracking.models import WorkoutLog

    jour = jour or datetime.date.today()
    log, _ = WorkoutLog.objects.get_or_create(
        user=user, workout_day=workout_day, date=jour
    )
    return log


def enregistrer_serie(workout_log, workout_exercise, serie_numero, repetitions_faites,
                      charge_kg, rpe=None):
    """Enregistre (ou met à jour) une série réalisée."""
    from tracking.models import SetLog

    setlog, _ = SetLog.objects.update_or_create(
        workout_log=workout_log,
        workout_exercise=workout_exercise,
        serie_numero=serie_numero,
        defaults={
            "repetitions_faites": repetitions_faites,
            "charge_kg": charge_kg,
            "rpe": rpe,
        },
    )
    return setlog
