"""Recettes prédéfinies utilisées en repli quand l'API Claude est indisponible.

La structure d'une recette est identique à celle attendue de l'IA :
`{nom, description, instructions, temps_preparation_min, portions,
  calories, proteines_g, glucides_g, lipides_g, ingredients:[{nom,quantite,unite}], tags}`.

Recettes volontairement simples, halal et sans allergène majeur courant
(pas d'arachide ni de fruits de mer), pour rester un repli sûr par défaut.
"""

from __future__ import annotations

_POOL = [
    {
        "nom": "Poulet, riz et brocoli",
        "description": "Assiette équilibrée classique, riche en protéines.",
        "instructions": (
            "1. Cuire le riz selon les instructions du paquet.\n"
            "2. Saisir le poulet coupé en dés 6-8 min avec un peu d'huile d'olive.\n"
            "3. Cuire le brocoli à la vapeur 5 min.\n"
            "4. Assembler, assaisonner (sel, poivre, paprika)."
        ),
        "temps_preparation_min": 20,
        "portions": 1,
        "calories": 550,
        "proteines_g": 45,
        "glucides_g": 55,
        "lipides_g": 14,
        "ingredients": [
            {"nom": "Blanc de poulet", "quantite": "150", "unite": "g"},
            {"nom": "Riz basmati (cru)", "quantite": "70", "unite": "g"},
            {"nom": "Brocoli", "quantite": "150", "unite": "g"},
            {"nom": "Huile d'olive", "quantite": "1", "unite": "c. à soupe"},
        ],
        "tags": ["prise_de_masse", "rapide", "halal"],
    },
    {
        "nom": "Omelette aux légumes et fromage",
        "description": "Repas rapide riche en protéines, idéal petit-déjeuner.",
        "instructions": (
            "1. Battre les œufs.\n"
            "2. Faire revenir les poivrons et oignons 3 min.\n"
            "3. Verser les œufs, ajouter le fromage, cuire à feu doux.\n"
            "4. Plier et servir."
        ),
        "temps_preparation_min": 10,
        "portions": 1,
        "calories": 400,
        "proteines_g": 30,
        "glucides_g": 8,
        "lipides_g": 28,
        "ingredients": [
            {"nom": "Œufs", "quantite": "3", "unite": "unités"},
            {"nom": "Poivron", "quantite": "1/2", "unite": "unité"},
            {"nom": "Fromage râpé", "quantite": "30", "unite": "g"},
        ],
        "tags": ["seche", "rapide", "halal", "vegetarien"],
    },
    {
        "nom": "Bowl de lentilles et patate douce",
        "description": "Source de protéines végétales et de glucides complexes.",
        "instructions": (
            "1. Cuire les lentilles 20 min.\n"
            "2. Rôtir la patate douce en dés au four 25 min à 200°C.\n"
            "3. Mélanger, ajouter un filet d'huile d'olive et des épices."
        ),
        "temps_preparation_min": 30,
        "portions": 1,
        "calories": 480,
        "proteines_g": 22,
        "glucides_g": 75,
        "lipides_g": 10,
        "ingredients": [
            {"nom": "Lentilles (crues)", "quantite": "80", "unite": "g"},
            {"nom": "Patate douce", "quantite": "200", "unite": "g"},
            {"nom": "Huile d'olive", "quantite": "1", "unite": "c. à soupe"},
        ],
        "tags": ["prise_de_masse", "batch_cooking", "halal", "vegetarien", "vegan"],
    },
    {
        "nom": "Skyr, flocons d'avoine et fruits",
        "description": "Collation protéinée rapide à préparer.",
        "instructions": (
            "1. Mélanger le skyr et les flocons d'avoine.\n"
            "2. Ajouter les fruits coupés et un peu de miel."
        ),
        "temps_preparation_min": 5,
        "portions": 1,
        "calories": 350,
        "proteines_g": 28,
        "glucides_g": 50,
        "lipides_g": 5,
        "ingredients": [
            {"nom": "Skyr nature", "quantite": "200", "unite": "g"},
            {"nom": "Flocons d'avoine", "quantite": "40", "unite": "g"},
            {"nom": "Banane", "quantite": "1", "unite": "unité"},
        ],
        "tags": ["seche", "rapide", "halal", "vegetarien"],
    },
]


def build_fallback_recipes(meal, n: int = 3) -> list[dict]:
    """Renvoie `n` recettes de repli (cycle sur le pool si n dépasse sa taille)."""
    if n <= 0:
        return []
    return [dict(_POOL[i % len(_POOL)]) for i in range(n)]
