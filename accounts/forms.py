from django import forms
from django.utils import timezone

from .models import Profile

# Champs de type « choix » dont on impose une sélection explicite : on retire
# la valeur par défaut du modèle pour forcer l'utilisateur à répondre lui-même
# (sinon on collecte un défaut silencieux qui fausse le programme proposé).
PLACEHOLDERS_CHOIX = {
    "sexe": "Sélectionne…",
    "objectif": "Quel est ton objectif ?",
    "niveau": "Ton niveau actuel",
    "activite": "Ton niveau d'activité au quotidien",
    "materiel": "Matériel dont tu disposes",
}

# Bornes de plausibilité pour la date de naissance (en années).
AGE_MIN = 13
AGE_MAX = 100

# Le style des champs (fond sombre, focus, etc.) est entièrement géré par la
# classe CSS .form-dark posée sur le conteneur du formulaire (cf. base.html) :
# on ne met donc PAS de classes Tailwind sur les widgets, seulement les
# attributs fonctionnels (bornes, type, placeholder).


class ProfileForm(forms.ModelForm):
    """Formulaire d'onboarding : profil sportif + nombre de repas du plan."""

    nombre_repas = forms.TypedChoiceField(
        label="Nombre de repas par jour",
        help_text="Répartit tes macros sur la journée.",
        coerce=int,
        choices=[(n, str(n)) for n in range(3, 7)],
        initial=4,
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
        # Explications courtes (sans jargon) sur les champs qui pilotent le
        # calcul des calories/macros et la génération du programme.
        help_texts = {
            "objectif": "Détermine tes calories cibles (surplus, déficit ou maintien).",
            "activite": "Estime les calories que tu brûles au quotidien, en dehors du sport.",
            "niveau": "Adapte le volume et le choix des exercices.",
            "jours_entrainement_par_semaine": "Définit comment tes séances sont réparties dans la semaine.",
            "materiel": "Filtre les exercices proposés.",
        }
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "taille_cm": forms.NumberInput(attrs={"min": 120, "max": 230}),
            "poids_kg": forms.NumberInput(attrs={"step": "0.1", "min": 30}),
            "jours_entrainement_par_semaine": forms.NumberInput(attrs={"min": 2, "max": 6}),
            "preferences_alimentaires": forms.Textarea(
                attrs={"rows": 2, "placeholder": "ex: halal, sans porc"}
            ),
            "allergies_alimentaires": forms.Textarea(
                attrs={"rows": 2, "placeholder": "ex: arachides, lactose"}
            ),
            "blessures_limitations": forms.Textarea(
                attrs={"rows": 2, "placeholder": "ex: épaule droite fragile"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Impose un choix explicite : option vide en tête, aucun pré-sélectionné.
        for nom, placeholder in PLACEHOLDERS_CHOIX.items():
            champ = self.fields[nom]
            champ.required = True
            champ.choices = [("", placeholder)] + [
                choix for choix in champ.choices if choix[0] != ""
            ]
            # On n'impose un défaut vide que pour un nouveau profil ; en édition,
            # la valeur de l'instance reste pré-remplie.
            if not (self.instance and self.instance.pk):
                self.initial.setdefault(nom, "")

    def clean_date_naissance(self):
        date_naissance = self.cleaned_data["date_naissance"]
        aujourdhui = timezone.localdate()
        if date_naissance > aujourdhui:
            raise forms.ValidationError("La date de naissance ne peut pas être dans le futur.")
        age = (aujourdhui - date_naissance).days // 365
        if not AGE_MIN <= age <= AGE_MAX:
            raise forms.ValidationError(
                f"L'âge doit être compris entre {AGE_MIN} et {AGE_MAX} ans."
            )
        return date_naissance

    def clean_jours_entrainement_par_semaine(self):
        valeur = self.cleaned_data["jours_entrainement_par_semaine"]
        if not 2 <= valeur <= 6:
            raise forms.ValidationError("Choisis entre 2 et 6 jours d'entraînement par semaine.")
        return valeur
