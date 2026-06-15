from django import template

register = template.Library()

# Classes Tailwind par groupe musculaire (badge coloré).
COULEURS_GROUPE = {
    "pectoraux": "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/20",
    "dos": "bg-blue-500/15 text-blue-300 ring-1 ring-blue-500/20",
    "jambes": "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/20",
    "epaules": "bg-violet-500/15 text-violet-300 ring-1 ring-violet-500/20",
    "biceps": "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/20",
    "triceps": "bg-teal-500/15 text-teal-300 ring-1 ring-teal-500/20",
    "abdos": "bg-orange-500/15 text-orange-300 ring-1 ring-orange-500/20",
    "mollets": "bg-lime-500/15 text-lime-300 ring-1 ring-lime-500/20",
}


@register.filter
def badge_groupe(valeur):
    """Classes Tailwind du badge pour un groupe musculaire (repli neutre)."""
    return COULEURS_GROUPE.get(valeur, "bg-surface-2 text-muted ring-1 ring-border")
