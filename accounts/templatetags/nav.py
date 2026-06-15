"""Tags de navigation de l'enveloppe applicative (sidebar)."""

from django import template

register = template.Library()


@register.filter
def est_actif(view_name, cibles):
    """Vrai si la vue courante figure parmi les cibles d'un lien de nav.

    `view_name` est `request.resolver_match.view_name` (ex: "tracking:dashboard").
    `cibles` est une chaîne de noms de vues séparés par des espaces : permet à un
    lien de rester surligné depuis ses sous-pages (ex: la bibliothèque reste active
    sur la fiche d'un exercice). Comparaison exacte, pas de matching de sous-chaîne.
    """
    if not view_name:
        return False
    return view_name in cibles.split()
