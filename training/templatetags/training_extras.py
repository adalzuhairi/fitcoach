from django import template

register = template.Library()

# Classes Tailwind par groupe musculaire (badge coloré).
COULEURS_GROUPE = {
    "pectoraux": "bg-rose-100 text-rose-700",
    "dos": "bg-blue-100 text-blue-700",
    "jambes": "bg-amber-100 text-amber-700",
    "epaules": "bg-violet-100 text-violet-700",
    "biceps": "bg-emerald-100 text-emerald-700",
    "triceps": "bg-teal-100 text-teal-700",
    "abdos": "bg-orange-100 text-orange-700",
    "mollets": "bg-lime-100 text-lime-700",
}


@register.filter
def badge_groupe(valeur):
    """Classes Tailwind du badge pour un groupe musculaire (repli neutre)."""
    return COULEURS_GROUPE.get(valeur, "bg-slate-100 text-slate-700")
