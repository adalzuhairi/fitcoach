"""Logique métier de l'app nutrition.

Formules de calcul codées en dur (PAS via IA), cf. CLAUDE.md :
- BMR via Mifflin-St Jeor
- TDEE = BMR × facteur d'activité
- calories cibles selon l'objectif
- répartition des macronutriments

Les fonctions de bas niveau prennent des primitives (facilement testables) ;
`calculer_objectifs_nutritionnels(profile)` orchestre le tout à partir d'un Profile.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.db import transaction

from accounts.models import FACTEURS_ACTIVITE, Objectif, Sexe

# Calories par gramme de macronutriment.
KCAL_PAR_G_PROTEINE = 4
KCAL_PAR_G_GLUCIDE = 4
KCAL_PAR_G_LIPIDE = 9

# Ajustements caloriques par objectif (kcal/jour, milieu des fourchettes CLAUDE.md).
AJUSTEMENT_CALORIQUE = {
    Objectif.PRISE_DE_MASSE: 300,   # TDEE + 250 à 350
    Objectif.SECHE: -450,           # TDEE − 400 à 500
    Objectif.RECOMPOSITION: 0,      # TDEE
    Objectif.MAINTIEN: 0,           # TDEE
    Objectif.FORCE: 150,            # TDEE + 100 à 200
}

# Protéines en g/kg de poids de corps (1,8 à 2,2 ; 2,2 en sèche).
PROTEINES_G_PAR_KG = 2.0
PROTEINES_G_PAR_KG_SECHE = 2.2

# Lipides en g/kg de poids de corps (0,8 à 1 ; plancher 0,6).
LIPIDES_G_PAR_KG = 0.8
LIPIDES_G_PAR_KG_MIN = 0.6


@dataclass(frozen=True)
class ObjectifsNutritionnels:
    """Résultat d'un calcul nutritionnel complet."""

    tdee: int
    calories_cibles: int
    proteines_g: int
    glucides_g: int
    lipides_g: int


def calculer_age(date_naissance: datetime.date, aujourdhui: datetime.date | None = None) -> int:
    """Âge en années révolues. `aujourdhui` est injectable pour les tests."""
    aujourdhui = aujourdhui or datetime.date.today()
    age = aujourdhui.year - date_naissance.year
    # Retire une année si l'anniversaire n'est pas encore passé cette année.
    if (aujourdhui.month, aujourdhui.day) < (date_naissance.month, date_naissance.day):
        age -= 1
    return age


def calculer_bmr(sexe: str, poids_kg: float, taille_cm: float, age: int) -> float:
    """Métabolisme de base (Mifflin-St Jeor), en kcal/jour."""
    base = 10 * poids_kg + 6.25 * taille_cm - 5 * age
    return base + (5 if sexe == Sexe.HOMME else -161)


def calculer_tdee(bmr: float, activite: str) -> float:
    """Dépense énergétique journalière totale (BMR × facteur d'activité)."""
    return bmr * FACTEURS_ACTIVITE[activite]


def calculer_calories_cibles(tdee: float, objectif: str) -> int:
    """Calories cibles journalières selon l'objectif, arrondies."""
    return round(tdee + AJUSTEMENT_CALORIQUE[objectif])


def calculer_macros(calories_cibles: int, poids_kg: float, objectif: str) -> dict[str, int]:
    """Répartition protéines / lipides / glucides en grammes.

    Protéines et lipides sont fixés au g/kg, les glucides absorbent le reste
    des calories. Si le reste est négatif (déficit serré), on réduit les lipides
    jusqu'à leur plancher avant de borner les glucides à 0.
    """
    prot_par_kg = PROTEINES_G_PAR_KG_SECHE if objectif == Objectif.SECHE else PROTEINES_G_PAR_KG
    proteines_g = round(prot_par_kg * poids_kg)
    lipides_g = round(LIPIDES_G_PAR_KG * poids_kg)

    cal_proteines = proteines_g * KCAL_PAR_G_PROTEINE
    cal_lipides = lipides_g * KCAL_PAR_G_LIPIDE
    cal_restantes = calories_cibles - cal_proteines - cal_lipides

    if cal_restantes < 0:
        # Réduit les lipides jusqu'au plancher 0,6 g/kg pour libérer des calories.
        lipides_g = round(LIPIDES_G_PAR_KG_MIN * poids_kg)
        cal_lipides = lipides_g * KCAL_PAR_G_LIPIDE
        cal_restantes = calories_cibles - cal_proteines - cal_lipides

    glucides_g = max(0, round(cal_restantes / KCAL_PAR_G_GLUCIDE))

    return {"proteines_g": proteines_g, "glucides_g": glucides_g, "lipides_g": lipides_g}


def calculer_objectifs_nutritionnels(profile, aujourdhui: datetime.date | None = None) -> ObjectifsNutritionnels:
    """Calcule TDEE, calories cibles et macros à partir d'un accounts.Profile."""
    age = calculer_age(profile.date_naissance, aujourdhui)
    poids = float(profile.poids_kg)
    taille = float(profile.taille_cm)

    bmr = calculer_bmr(profile.sexe, poids, taille, age)
    tdee = calculer_tdee(bmr, profile.activite)
    calories_cibles = calculer_calories_cibles(tdee, profile.objectif)
    macros = calculer_macros(calories_cibles, poids, profile.objectif)

    return ObjectifsNutritionnels(
        tdee=round(tdee),
        calories_cibles=calories_cibles,
        **macros,
    )


# Répartition des repas par fraction des apports journaliers.
# Les fractions de chaque ligne somment à 1,0.
REPARTITION_REPAS = {
    3: [("Petit-déjeuner", 0.30), ("Déjeuner", 0.40), ("Dîner", 0.30)],
    4: [("Petit-déjeuner", 0.25), ("Déjeuner", 0.35), ("Collation", 0.15), ("Dîner", 0.25)],
    5: [
        ("Petit-déjeuner", 0.25),
        ("Déjeuner", 0.30),
        ("Collation", 0.10),
        ("Dîner", 0.25),
        ("Collation du soir", 0.10),
    ],
    6: [
        ("Petit-déjeuner", 0.20),
        ("Collation du matin", 0.10),
        ("Déjeuner", 0.30),
        ("Collation de l'après-midi", 0.10),
        ("Dîner", 0.20),
        ("Collation du soir", 0.10),
    ],
}


def repartir_repas(objectifs: ObjectifsNutritionnels, nombre_repas: int) -> list[dict]:
    """Répartit calories et macros sur les repas de la journée.

    Tous les repas sauf le dernier sont arrondis à partir de leur fraction ;
    le dernier absorbe le reste afin que les totaux correspondent exactement
    aux objectifs (pas de dérive d'arrondi).
    """
    repartition = REPARTITION_REPAS[nombre_repas]
    totaux = {
        "calories": objectifs.calories_cibles,
        "proteines_g": objectifs.proteines_g,
        "glucides_g": objectifs.glucides_g,
        "lipides_g": objectifs.lipides_g,
    }
    cumul = {cle: 0 for cle in totaux}
    repas = []

    for index, (nom, fraction) in enumerate(repartition):
        dernier = index == len(repartition) - 1
        ligne = {"nom": nom, "ordre": index + 1}
        for cle, total in totaux.items():
            if dernier:
                valeur = total - cumul[cle]
            else:
                valeur = round(total * fraction)
                cumul[cle] += valeur
            ligne[cle] = valeur
        repas.append(ligne)

    return repas


@transaction.atomic
def creer_plan_nutritionnel(user, profile, nombre_repas: int = 4, aujourdhui=None):
    """Calcule les objectifs, désactive l'ancien plan actif et crée le nouveau.

    Crée également les repas (Meal) selon la répartition. Tout est fait dans
    une transaction pour garantir la cohérence.
    """
    # Import local pour éviter tout cycle au chargement du module.
    from nutrition.models import Meal, NutritionPlan

    objectifs = calculer_objectifs_nutritionnels(profile, aujourdhui)

    NutritionPlan.objects.filter(user=user, actif=True).update(actif=False)
    plan = NutritionPlan.objects.create(
        user=user,
        actif=True,
        tdee_calcule=objectifs.tdee,
        calories_cibles=objectifs.calories_cibles,
        proteines_g=objectifs.proteines_g,
        glucides_g=objectifs.glucides_g,
        lipides_g=objectifs.lipides_g,
        nombre_repas=nombre_repas,
    )

    Meal.objects.bulk_create(
        Meal(
            plan=plan,
            nom=r["nom"],
            ordre=r["ordre"],
            calories=r["calories"],
            proteines_g=r["proteines_g"],
            glucides_g=r["glucides_g"],
            lipides_g=r["lipides_g"],
        )
        for r in repartir_repas(objectifs, nombre_repas)
    )
    return plan


# Mots-clés de préférences alimentaires → tag de recette correspondant.
# Les préférences déclarées au profil filtrent strictement les suggestions.
PREFERENCE_TAGS = {
    "halal": "halal",
    "casher": "casher",
    "kasher": "casher",
    "vegetarien": "vegetarien",
    "végétarien": "vegetarien",
    "vegan": "vegan",
    "végan": "vegan",
    "végétalien": "vegan",
}


def preferences_requises(profile) -> set[str]:
    """Tags de recette imposés par les préférences alimentaires du profil."""
    texte = (profile.preferences_alimentaires or "").lower()
    return {tag for mot, tag in PREFERENCE_TAGS.items() if mot in texte}


def recettes_suggerees(profile, limit: int = 6) -> list:
    """Recettes du catalogue pertinentes pour l'objectif et les préférences.

    Filtrage en Python (catalogue restreint, portable SQLite/Postgres) :
    - écarte toute recette qui ne respecte pas une préférence imposée
      (ex: « végétarien » exige le tag `vegetarien`) ;
    - place en tête les recettes taguées avec l'objectif de l'utilisateur,
      puis complète avec le reste jusqu'à `limit`.
    """
    from nutrition.models import Recipe

    requises = preferences_requises(profile)
    objectif = profile.objectif
    prioritaires: list = []
    autres: list = []

    for recipe in Recipe.objects.all():
        tags = {str(t).lower() for t in (recipe.tags or [])}
        if requises and not requises.issubset(tags):
            continue
        (prioritaires if objectif in tags else autres).append(recipe)

    return (prioritaires + autres)[:limit]
