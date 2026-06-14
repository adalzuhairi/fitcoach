import datetime

from django import forms

from .models import BodyMeasurement

# Classes Tailwind communes (alignées sur accounts/forms.py).
INPUT_CLASS = (
    "w-full rounded-xl border border-slate-300 px-3 py-2 text-slate-800 "
    "focus:border-accent focus:ring-2 focus:ring-accent/30 focus:outline-none"
)


class BodyMeasurementForm(forms.ModelForm):
    """Saisie d'une pesée : poids obligatoire, mensurations et photo optionnelles.

    Le champ `user` est exclu : il est posé par la vue/le service. Comme `user`
    ne fait pas partie du formulaire, Django n'applique pas la contrainte
    unique_together (user, date) — la même date est gérée en *update* côté service.
    """

    class Meta:
        model = BodyMeasurement
        fields = [
            "date",
            "poids_kg",
            "tour_taille",
            "tour_bras",
            "tour_poitrine",
            "tour_cuisses",
            "photo",
        ]
        widgets = {
            "date": forms.DateInput(
                attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"
            ),
            "poids_kg": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "step": "0.1", "min": 30, "placeholder": "kg"}
            ),
            "tour_taille": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.1", "min": 0}),
            "tour_bras": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.1", "min": 0}),
            "tour_poitrine": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.1", "min": 0}),
            "tour_cuisses": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.1", "min": 0}),
            "photo": forms.ClearableFileInput(attrs={"class": "text-sm text-slate-500"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pré-remplit la date du jour pour une saisie rapide (création seulement).
        if not self.instance.pk and not self.initial.get("date"):
            self.initial["date"] = datetime.date.today()
