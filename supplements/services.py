"""Logique métier de l'app suppléments (recommandation SANS IA).

Principe : une table de correspondance objectif → catégories pertinentes
(ordonnées par priorité), filtrée selon les préférences alimentaires du profil
(réutilise nutrition.services.preferences_requises) puis triée par niveau de
preuve scientifique. Aucune dépendance à l'API : tout est déterministe et testable.
"""

from __future__ import annotations

from accounts.models import Objectif
from nutrition.services import preferences_requises

from .models import Categorie, NiveauPreuve, Supplement

# Catégories conseillées par objectif, ordonnées par priorité (1re = la plus pertinente).
# Choix fondés sur le consensus, pas sur le marketing ; le détail vit dans la fixture.
RECO_PAR_OBJECTIF: dict[str, list[str]] = {
    Objectif.PRISE_DE_MASSE: [
        Categorie.CREATINE,
        Categorie.PROTEINE,
        Categorie.GAINER,
        Categorie.OMEGA3,
        Categorie.VITAMINES_MINERAUX,
    ],
    Objectif.SECHE: [
        Categorie.PROTEINE,
        Categorie.CREATINE,
        Categorie.PRE_WORKOUT,
        Categorie.OMEGA3,
        Categorie.VITAMINES_MINERAUX,
    ],
    Objectif.RECOMPOSITION: [
        Categorie.PROTEINE,
        Categorie.CREATINE,
        Categorie.OMEGA3,
        Categorie.VITAMINES_MINERAUX,
    ],
    Objectif.FORCE: [
        Categorie.CREATINE,
        Categorie.PROTEINE,
        Categorie.PRE_WORKOUT,
        Categorie.OMEGA3,
    ],
    Objectif.MAINTIEN: [
        Categorie.PROTEINE,
        Categorie.OMEGA3,
        Categorie.VITAMINES_MINERAUX,
    ],
}

# Tri secondaire : les preuves solides remontent (honnêteté scientifique).
_ORDRE_PREUVE = {
    NiveauPreuve.ELEVE: 0,
    NiveauPreuve.MODERE: 1,
    NiveauPreuve.FAIBLE: 2,
}


def recommander_complements(profile) -> list[Supplement]:
    """Compléments conseillés pour le profil, filtrés et triés par pertinence.

    - ne garde que les catégories pertinentes pour l'objectif du profil ;
    - exclut les compléments incompatibles avec le régime alimentaire
      (ex. whey si vegan), via `exclu_pour` ∩ `preferences_requises(profile)` ;
    - trie par priorité d'objectif (ordre des catégories), puis par niveau de preuve.
    """
    if profile is None:
        return []

    categories = RECO_PAR_OBJECTIF.get(profile.objectif, [])
    if not categories:
        return []

    rang_categorie = {cat: i for i, cat in enumerate(categories)}
    regimes = preferences_requises(profile)

    candidats = Supplement.objects.filter(actif=True, categorie__in=categories)
    retenus = [s for s in candidats if not (set(s.exclu_pour or []) & regimes)]
    retenus.sort(
        key=lambda s: (
            rang_categorie[s.categorie],
            s.priorite,
            _ORDRE_PREUVE.get(s.niveau_preuve, 9),
            s.nom,
        )
    )
    return retenus
