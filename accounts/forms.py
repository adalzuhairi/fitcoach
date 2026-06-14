from django import forms

from .models import Profile

# Classes Tailwind communes aux champs du formulaire.
INPUT_CLASS = (
    "w-full rounded-xl border border-slate-300 px-3 py-2 text-slate-800 "
    "focus:border-accent focus:ring-2 focus:ring-accent/30 focus:outline-none"
)
TEXTAREA_CLASS = INPUT_CLASS + " min-h-[80px]"


class ProfileForm(forms.ModelForm):
    """Formulaire d'onboarding : profil sportif + nombre de repas du plan."""

    nombre_repas = forms.TypedChoiceField(
        label="Nombre de repas par jour",
        coerce=int,
        choices=[(n, str(n)) for n in range(3, 7)],
        initial=4,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    class Meta:
        model = Profile
        fields = [
            "sexe",
            "date_naissance",
            "taille_cm",
            "poids_kg",
            "objectif",
            "niveau",
            "activite",
            "jours_entrainement_par_semaine",
            "materiel",
            "preferences_alimentaires",
            "allergies_alimentaires",
            "blessures_limitations",
        ]
        widgets = {
            "sexe": forms.Select(attrs={"class": INPUT_CLASS}),
            "date_naissance": forms.DateInput(
                attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"
            ),
            "taille_cm": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 120, "max": 230}),
            "poids_kg": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.1", "min": 30}),
            "objectif": forms.Select(attrs={"class": INPUT_CLASS}),
            "niveau": forms.Select(attrs={"class": INPUT_CLASS}),
            "activite": forms.Select(attrs={"class": INPUT_CLASS}),
            "jours_entrainement_par_semaine": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "min": 2, "max": 6}
            ),
            "materiel": forms.Select(attrs={"class": INPUT_CLASS}),
            "preferences_alimentaires": forms.Textarea(
                attrs={"class": TEXTAREA_CLASS, "rows": 2, "placeholder": "ex: halal, sans porc"}
            ),
            "allergies_alimentaires": forms.Textarea(
                attrs={"class": TEXTAREA_CLASS, "rows": 2, "placeholder": "ex: arachides, lactose"}
            ),
            "blessures_limitations": forms.Textarea(
                attrs={"class": TEXTAREA_CLASS, "rows": 2, "placeholder": "ex: épaule droite fragile"}
            ),
        }

    def clean_jours_entrainement_par_semaine(self):
        valeur = self.cleaned_data["jours_entrainement_par_semaine"]
        if not 2 <= valeur <= 6:
            raise forms.ValidationError("Choisis entre 2 et 6 jours d'entraînement par semaine.")
        return valeur
