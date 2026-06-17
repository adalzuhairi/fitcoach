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

from accounts.models import Materiel, Niveau

from .models import Exercise, GroupeMusculaire, ProgressionType, WorkoutExercise

# Groupes considérés comme "bas du corps" pour l'incrément de charge.
GROUPES_BAS_DU_CORPS = {GroupeMusculaire.JAMBES, GroupeMusculaire.MOLLETS}

INCREMENT_HAUT = Decimal("2.5")
INCREMENT_BAS = Decimal("5")

# Ordre des niveaux pour comparer « niveau de l'exercice ≤ niveau de l'utilisateur ».
NIVEAUX_ORDRE = {Niveau.DEBUTANT: 0, Niveau.INTERMEDIAIRE: 1, Niveau.AVANCE: 2}

# Matériel accessible selon ce dont dispose l'utilisateur : une salle complète
# permet tout, des haltères maison permettent haltères + poids du corps, le
# poids du corps ne permet que lui-même.
MATERIEL_ACCESSIBLE = {
    Materiel.SALLE_COMPLETE: {
        Materiel.SALLE_COMPLETE,
        Materiel.HALTERES_MAISON,
        Materiel.POIDS_DU_CORPS,
    },
    Materiel.HALTERES_MAISON: {Materiel.HALTERES_MAISON, Materiel.POIDS_DU_CORPS},
    Materiel.POIDS_DU_CORPS: {Materiel.POIDS_DU_CORPS},
}


def alternatives_exercice(workout_exercise, profile, limit=8):
    """Alternatives à un exercice pour une substitution de séance (même muscle).

    Repli en cascade pour ne jamais laisser l'utilisateur sans option à la salle
    (catalogue limité + matériel restreint donnent parfois peu de candidats) :
      1. même groupe musculaire, matériel compatible, niveau ≤ celui du profil ;
      2. on relâche le niveau (tous niveaux), matériel toujours compatible ;
      3. on relâche le matériel — chaque candidat est alors marqué
         `materiel_different` pour afficher honnêtement « peut nécessiter un
         autre matériel ».
    Exclut l'exercice courant et les exercices encore à valider (`a_valider`).
    Renvoie une liste de dicts {exercise, materiel_different} ; vide seulement si
    le groupe ne contient aucun autre exercice.
    """
    exo_courant = workout_exercise.exercise
    candidats = list(
        Exercise.objects.filter(
            groupe_musculaire=exo_courant.groupe_musculaire, a_valider=False
        )
        .exclude(pk=exo_courant.pk)
        .order_by("type", "nom")  # composés d'abord, puis ordre alphabétique
    )
    if not candidats:
        return []

    materiel_user = profile.materiel if profile else Materiel.SALLE_COMPLETE
    accessibles = MATERIEL_ACCESSIBLE.get(materiel_user, {materiel_user})
    niveau_max = NIVEAUX_ORDRE.get(profile.niveau, 2) if profile else 2

    def materiel_ok(ex):
        return ex.materiel_requis in accessibles

    def niveau_ok(ex):
        return NIVEAUX_ORDRE.get(ex.niveau_minimum, 0) <= niveau_max

    etape1 = [e for e in candidats if materiel_ok(e) and niveau_ok(e)]
    if etape1:
        return [{"exercise": e, "materiel_different": False} for e in etape1[:limit]]

    etape2 = [e for e in candidats if materiel_ok(e)]
    if etape2:
        return [{"exercise": e, "materiel_different": False} for e in etape2[:limit]]

    return [
        {"exercise": e, "materiel_different": not materiel_ok(e)}
        for e in candidats[:limit]
    ]


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


def _historique_effectif(user, exercise):
    """Séries de l'utilisateur dont l'exercice EFFECTIF est `exercise`.

    Tient compte des substitutions de séance : une série loggée sur un créneau
    substitué ce jour-là est attribuée au substitut, pas à l'exercice du
    programme. Renvoie une liste de SetLog (avec leur séance préchargée).
    """
    # Imports locaux pour éviter une dépendance circulaire training <-> tracking.
    from tracking.models import SetLog
    from tracking.services import substitutions_map

    subs = substitutions_map(user)
    sets = []
    for s in SetLog.objects.filter(workout_log__user=user).select_related(
        "workout_log", "workout_exercise"
    ):
        effectif = subs.get(
            (s.workout_log_id, s.workout_exercise_id), s.workout_exercise.exercise_id
        )
        if effectif == exercise.id:
            sets.append(s)
    return sets


def suggestion_charge(
    workout_exercise: WorkoutExercise, user, exercise_substitut=None
) -> Decimal | None:
    """Charge suggérée pour le prochain passage sur ce créneau.

    Se base sur l'historique de l'exercice réellement réalisé : si une
    substitution est active aujourd'hui (`exercise_substitut`), on suggère
    d'après l'historique du SUBSTITUT — et `None` s'il n'a jamais été loggé
    (pas de suggestion hasardeuse pour un mouvement inconnu). Sans substitution,
    on se base sur l'exercice du programme. L'historique est « effectif » : les
    séries d'anciennes séances substituées ne polluent pas la suggestion.

    Applique la double progression : si toutes les séries de la dernière séance
    ont atteint le haut de la fourchette, on ajoute l'incrément (lié au groupe
    musculaire de l'exercice réalisé) ; sinon on reprend sa charge max.
    """
    exercise = exercise_substitut or workout_exercise.exercise
    sets = _historique_effectif(user, exercise)
    if not sets:
        return None

    derniere_date = max(s.workout_log.date for s in sets)
    sets_dernier = [s for s in sets if s.workout_log.date == derniere_date]
    charge_max = max(s.charge_kg for s in sets_dernier)

    top = reps_max(workout_exercise.repetitions)
    progression_ok = (
        workout_exercise.progression_type == ProgressionType.DOUBLE_PROGRESSION
        and top is not None
        and all(s.repetitions_faites >= top for s in sets_dernier)
    )
    if progression_ok:
        return charge_max + increment_charge(exercise.groupe_musculaire)
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
