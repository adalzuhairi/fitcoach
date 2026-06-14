"""Intégration de l'API Anthropic (Claude) — service layer.

`generate_program(profile)` : génère un programme d'entraînement personnalisé.
- Construit un prompt structuré (objectif, niveau, jours/semaine, matériel, blessures)
- Demande une réponse JSON stricte via structured outputs (output_config.format)
- Mappe les exercices retournés sur la table Exercise (création si absent, à valider)
- Sauvegarde le programme complet en une transaction
- Cache Redis pour éviter les appels redondants
- try/except + retry (1 fois) + fallback sur des templates prédéfinis si l'API échoue

Règles : clé via ANTHROPIC_API_KEY, SDK officiel `anthropic`, modèle configurable
(claude-sonnet-4-6 par défaut, cf. CLAUDE.md).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from accounts.models import Niveau
from training.models import (
    DureeSemaines,
    Exercise,
    GroupeMusculaire,
    Program,
    Split,
    TypeExercice,
    WorkoutDay,
    WorkoutExercise,
)

from .fallback_programs import build_fallback_program

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Tu es un coach sportif et nutritionniste expérimenté. "
    "Réponds UNIQUEMENT en JSON valide, sans markdown."
)

# Schéma JSON strict imposé à Claude (structured outputs).
PROGRAM_SCHEMA = {
    "type": "object",
    "properties": {
        "split": {
            "type": "string",
            "enum": [s.value for s in Split],
        },
        "jours": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string"},
                    "exercices": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nom": {"type": "string"},
                                "groupe_musculaire": {
                                    "type": "string",
                                    "enum": [g.value for g in GroupeMusculaire],
                                },
                                "series": {"type": "integer"},
                                "reps": {"type": "string"},
                                "repos_s": {"type": "integer"},
                                "notes": {"type": "string"},
                            },
                            "required": [
                                "nom",
                                "groupe_musculaire",
                                "series",
                                "reps",
                                "repos_s",
                                "notes",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["nom", "exercices"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["split", "jours"],
    "additionalProperties": False,
}

CACHE_TTL_SECONDES = 60 * 60 * 24 * 7  # 7 jours


def _build_prompt(profile) -> str:
    """Construit le prompt utilisateur à partir du profil sportif."""
    blessures = profile.blessures_limitations.strip() or "aucune"
    return (
        "Génère un programme de musculation personnalisé.\n\n"
        f"- Objectif : {profile.get_objectif_display()}\n"
        f"- Niveau : {profile.get_niveau_display()}\n"
        f"- Jours d'entraînement par semaine : {profile.jours_entrainement_par_semaine}\n"
        f"- Matériel disponible : {profile.get_materiel_display()}\n"
        f"- Blessures / limitations : {blessures}\n\n"
        "Contraintes :\n"
        "- Choisis un split adapté au nombre de jours.\n"
        "- Pour chaque jour, propose des exercices avec séries, répétitions "
        "(ex: \"8-12\"), temps de repos en secondes et une note d'exécution courte.\n"
        "- Respecte les temps de repos usuels : composés lourds 150-180 s, "
        "composés modérés 90-120 s, isolation 60-90 s.\n"
        "- Adapte les exercices au matériel et évite ceux qui aggravent les blessures."
    )


def _cache_key(profile) -> str:
    """Clé de cache déterministe basée sur les facteurs qui influent sur le programme."""
    parts = "|".join(
        str(v)
        for v in (
            profile.objectif,
            profile.niveau,
            profile.jours_entrainement_par_semaine,
            profile.materiel,
            profile.blessures_limitations.strip(),
        )
    )
    digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()[:16]
    return f"coach:program:{digest}"


def _call_claude(prompt: str) -> dict:
    """Appelle l'API Claude et renvoie le programme en dict (JSON strict).

    Lève une exception si l'appel échoue ; la gestion du fallback est faite
    par l'appelant. Le SDK retente automatiquement (max_retries=1).
    """
    # Import local : évite de charger le SDK si on part directement en fallback.
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=1)
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {"type": "json_schema", "schema": PROGRAM_SCHEMA},
        },
    )
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)


def _get_program_data(profile) -> tuple[dict, str, bool]:
    """Récupère les données du programme : cache → Claude → fallback.

    Renvoie (data, prompt, genere_par_ia).
    """
    prompt = _build_prompt(profile)
    key = _cache_key(profile)

    cached = cache.get(key)
    if cached is not None:
        return cached, prompt, True

    if settings.ANTHROPIC_API_KEY:
        try:
            data = _call_claude(prompt)
            cache.set(key, data, CACHE_TTL_SECONDES)
            return data, prompt, True
        except Exception:  # noqa: BLE001 — on bascule sur le fallback quoi qu'il arrive
            logger.exception("Échec de la génération IA, bascule sur les templates")
    else:
        logger.warning("ANTHROPIC_API_KEY absente — utilisation des templates de fallback")

    return build_fallback_program(profile), prompt, False


def _resolved_split(valeur: str) -> str:
    """Valide la valeur de split renvoyée, avec repli sur full_body."""
    valides = {s.value for s in Split}
    return valeur if valeur in valides else Split.FULL_BODY


def _resolved_groupe(valeur: str) -> str:
    """Valide le groupe musculaire, avec repli sur pectoraux."""
    valides = {g.value for g in GroupeMusculaire}
    return valeur if valeur in valides else GroupeMusculaire.PECTORAUX


def _get_or_create_exercise(nom: str, groupe: str, profile) -> Exercise:
    """Mappe un exercice par nom (insensible à la casse) ; crée si absent (à valider)."""
    exercise = Exercise.objects.filter(nom__iexact=nom.strip()).first()
    if exercise is not None:
        return exercise
    return Exercise.objects.create(
        nom=nom.strip(),
        groupe_musculaire=_resolved_groupe(groupe),
        type=TypeExercice.COMPOSE,
        materiel_requis=profile.materiel,
        niveau_minimum=profile.niveau or Niveau.DEBUTANT,
        a_valider=True,  # exercice créé par l'IA, à valider par un admin
    )


@transaction.atomic
def generate_program(profile) -> Program:
    """Génère, mappe et sauvegarde un programme complet pour le profil donné.

    Désactive l'éventuel programme actif, puis crée le nouveau programme avec
    ses journées et exercices, le tout dans une transaction.
    """
    data, prompt, genere_par_ia = _get_program_data(profile)
    split = _resolved_split(data.get("split", ""))

    Program.objects.filter(user=profile.user, actif=True).update(actif=False)

    program = Program.objects.create(
        user=profile.user,
        nom=f"Programme {profile.get_objectif_display()} — {dict(Split.choices)[split]}",
        objectif=profile.objectif,
        date_debut=datetime.date.today(),
        duree_semaines=DureeSemaines.HUIT,
        split=split,
        actif=True,
        genere_par_ia=genere_par_ia,
        prompt_ia=prompt if genere_par_ia else "",
        reponse_ia=data,
    )

    for jour_index, jour in enumerate(data.get("jours", []), start=1):
        workout_day = WorkoutDay.objects.create(
            program=program,
            jour_numero=jour_index,
            nom=jour.get("nom", f"Jour {jour_index}"),
        )
        for ordre, exo in enumerate(jour.get("exercices", []), start=1):
            exercise = _get_or_create_exercise(
                exo["nom"], exo.get("groupe_musculaire", ""), profile
            )
            WorkoutExercise.objects.create(
                workout_day=workout_day,
                exercise=exercise,
                ordre=ordre,
                series=exo.get("series", 3),
                repetitions=str(exo.get("reps", "8-12")),
                temps_repos_secondes=exo.get("repos_s", 90),
                notes=exo.get("notes", ""),
            )

    return program
