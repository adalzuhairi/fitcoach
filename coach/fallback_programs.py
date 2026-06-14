"""Programmes prédéfinis utilisés en repli quand l'API Claude est indisponible.

Les noms d'exercices correspondent à ceux de la fixture `exercises.json`, afin que
le mapping (coach.services._get_or_create_exercise) les retrouve sans en créer.
La structure renvoyée est identique à celle attendue de l'IA :
`{"split": ..., "jours": [{"nom", "exercices": [{nom, groupe_musculaire, series, reps, repos_s, notes}]}]}`.
"""

from __future__ import annotations

from training.models import Split


def _exo(nom, groupe, series, reps, repos_s, notes=""):
    return {
        "nom": nom,
        "groupe_musculaire": groupe,
        "series": series,
        "reps": reps,
        "repos_s": repos_s,
        "notes": notes,
    }


# --- Journées réutilisables -------------------------------------------------

_PUSH = {
    "nom": "Push — Pectoraux / Épaules / Triceps",
    "exercices": [
        _exo("Développé couché barre", "pectoraux", 4, "6-10", 150),
        _exo("Développé incliné haltères", "pectoraux", 3, "8-12", 120),
        _exo("Développé militaire barre", "epaules", 4, "6-10", 150),
        _exo("Élévations latérales", "epaules", 3, "12-15", 60),
        _exo("Extension poulie haute", "triceps", 3, "10-15", 75),
    ],
}

_PULL = {
    "nom": "Pull — Dos / Biceps",
    "exercices": [
        _exo("Tractions pronation", "dos", 4, "6-10", 120),
        _exo("Rowing barre", "dos", 4, "8-12", 120),
        _exo("Tirage horizontal poulie", "dos", 3, "10-12", 90),
        _exo("Curl barre", "biceps", 3, "8-12", 75),
        _exo("Curl marteau", "biceps", 3, "10-12", 60),
    ],
}

_LEGS = {
    "nom": "Legs — Jambes / Mollets",
    "exercices": [
        _exo("Squat barre", "jambes", 4, "6-10", 180),
        _exo("Soulevé de terre roumain", "jambes", 3, "8-12", 150),
        _exo("Presse à cuisses", "jambes", 3, "10-12", 120),
        _exo("Leg curl allongé", "jambes", 3, "10-15", 75),
        _exo("Mollets debout", "mollets", 4, "12-20", 60),
    ],
}

_HAUT_A = {
    "nom": "Haut du corps A",
    "exercices": [
        _exo("Développé couché barre", "pectoraux", 4, "6-10", 150),
        _exo("Rowing barre", "dos", 4, "8-12", 120),
        _exo("Développé militaire barre", "epaules", 3, "8-12", 120),
        _exo("Curl barre", "biceps", 3, "8-12", 75),
        _exo("Extension poulie haute", "triceps", 3, "10-15", 75),
    ],
}

_BAS_A = {
    "nom": "Bas du corps A",
    "exercices": [
        _exo("Squat barre", "jambes", 4, "6-10", 180),
        _exo("Presse à cuisses", "jambes", 3, "10-12", 120),
        _exo("Leg curl allongé", "jambes", 3, "10-15", 75),
        _exo("Mollets debout", "mollets", 4, "12-20", 60),
    ],
}

_HAUT_B = {
    "nom": "Haut du corps B",
    "exercices": [
        _exo("Développé incliné haltères", "pectoraux", 4, "8-12", 120),
        _exo("Tractions pronation", "dos", 4, "6-10", 120),
        _exo("Élévations latérales", "epaules", 3, "12-15", 60),
        _exo("Curl marteau", "biceps", 3, "10-12", 60),
        _exo("Barre au front", "triceps", 3, "8-12", 90),
    ],
}

_BAS_B = {
    "nom": "Bas du corps B",
    "exercices": [
        _exo("Soulevé de terre roumain", "jambes", 4, "8-12", 150),
        _exo("Leg extension", "jambes", 3, "12-15", 75),
        _exo("Fentes haltères", "jambes", 3, "10-12", 90),
        _exo("Mollets assis", "mollets", 4, "15-20", 60),
    ],
}

_FULL_A = {
    "nom": "Full body A",
    "exercices": [
        _exo("Squat barre", "jambes", 4, "6-10", 180),
        _exo("Développé couché barre", "pectoraux", 4, "6-10", 150),
        _exo("Rowing barre", "dos", 3, "8-12", 120),
        _exo("Développé militaire barre", "epaules", 3, "8-12", 120),
        _exo("Curl barre", "biceps", 3, "10-12", 60),
    ],
}

_FULL_B = {
    "nom": "Full body B",
    "exercices": [
        _exo("Soulevé de terre", "dos", 3, "5-8", 180),
        _exo("Développé incliné haltères", "pectoraux", 3, "8-12", 120),
        _exo("Tirage vertical poulie", "dos", 3, "10-12", 90),
        _exo("Élévations latérales", "epaules", 3, "12-15", 60),
        _exo("Extension poulie haute", "triceps", 3, "10-15", 75),
    ],
}

_FULL_C = {
    "nom": "Full body C",
    "exercices": [
        _exo("Presse à cuisses", "jambes", 4, "10-12", 120),
        _exo("Dips pectoraux", "pectoraux", 3, "8-12", 120),
        _exo("Tractions pronation", "dos", 3, "6-10", 120),
        _exo("Leg curl allongé", "jambes", 3, "10-15", 75),
        _exo("Curl marteau", "biceps", 3, "10-12", 60),
    ],
}


def _split_classique_5():
    return [
        {
            "nom": "Pectoraux",
            "exercices": [
                _exo("Développé couché barre", "pectoraux", 4, "6-10", 150),
                _exo("Développé incliné haltères", "pectoraux", 3, "8-12", 120),
                _exo("Écarté couché haltères", "pectoraux", 3, "10-15", 75),
                _exo("Dips pectoraux", "pectoraux", 3, "8-12", 120),
            ],
        },
        {
            "nom": "Dos",
            "exercices": [
                _exo("Soulevé de terre", "dos", 3, "5-8", 180),
                _exo("Tractions pronation", "dos", 4, "6-10", 120),
                _exo("Rowing barre", "dos", 3, "8-12", 120),
                _exo("Tirage vertical poulie", "dos", 3, "10-12", 90),
            ],
        },
        {
            "nom": "Jambes",
            "exercices": [
                _exo("Squat barre", "jambes", 4, "6-10", 180),
                _exo("Presse à cuisses", "jambes", 3, "10-12", 120),
                _exo("Leg extension", "jambes", 3, "12-15", 75),
                _exo("Leg curl allongé", "jambes", 3, "10-15", 75),
                _exo("Mollets debout", "mollets", 4, "12-20", 60),
            ],
        },
        {
            "nom": "Épaules",
            "exercices": [
                _exo("Développé militaire barre", "epaules", 4, "6-10", 150),
                _exo("Élévations latérales", "epaules", 3, "12-15", 60),
                _exo("Oiseau", "epaules", 3, "12-15", 60),
                _exo("Face pull", "epaules", 3, "12-15", 60),
            ],
        },
        {
            "nom": "Bras",
            "exercices": [
                _exo("Curl barre", "biceps", 3, "8-12", 75),
                _exo("Curl marteau", "biceps", 3, "10-12", 60),
                _exo("Extension poulie haute", "triceps", 3, "10-15", 75),
                _exo("Barre au front", "triceps", 3, "8-12", 90),
            ],
        },
    ]


def build_fallback_program(profile) -> dict:
    """Renvoie un programme de repli adapté au nombre de jours d'entraînement."""
    jours = profile.jours_entrainement_par_semaine

    if jours <= 3:
        return {"split": Split.FULL_BODY, "jours": [_FULL_A, _FULL_B, _FULL_C][:max(jours, 2)]}
    if jours == 4:
        return {"split": Split.HALF_BODY, "jours": [_HAUT_A, _BAS_A, _HAUT_B, _BAS_B]}
    if jours == 5:
        return {"split": Split.SPLIT_CLASSIQUE, "jours": _split_classique_5()}
    # 6 jours et plus : Push / Pull / Legs sur deux cycles.
    return {
        "split": Split.PUSH_PULL_LEGS,
        "jours": [
            {**_PUSH, "nom": _PUSH["nom"] + " (A)"},
            {**_PULL, "nom": _PULL["nom"] + " (A)"},
            {**_LEGS, "nom": _LEGS["nom"] + " (A)"},
            {**_PUSH, "nom": _PUSH["nom"] + " (B)"},
            {**_PULL, "nom": _PULL["nom"] + " (B)"},
            {**_LEGS, "nom": _LEGS["nom"] + " (B)"},
        ],
    }
