from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Utilisateur personnalisé de FitCoach.

    On étend AbstractUser dès le départ pour pouvoir ajouter des champs
    propres au produit sans migration douloureuse par la suite. Le profil
    sportif détaillé vit dans accounts.Profile (OneToOne).
    """

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self) -> str:
        return self.get_full_name() or self.username


class Sexe(models.TextChoices):
    HOMME = "H", "Homme"
    FEMME = "F", "Femme"


class Niveau(models.TextChoices):
    DEBUTANT = "debutant", "Débutant"
    INTERMEDIAIRE = "intermediaire", "Intermédiaire"
    AVANCE = "avance", "Avancé"


class Objectif(models.TextChoices):
    PRISE_DE_MASSE = "prise_de_masse", "Prise de masse"
    SECHE = "seche", "Sèche"
    RECOMPOSITION = "recomposition", "Recomposition"
    FORCE = "force", "Force"
    MAINTIEN = "maintien", "Maintien"


class Activite(models.TextChoices):
    SEDENTAIRE = "sedentaire", "Sédentaire"
    LEGER = "leger", "Léger"
    MODERE = "modere", "Modéré"
    ACTIF = "actif", "Actif"
    TRES_ACTIF = "tres_actif", "Très actif"


class Materiel(models.TextChoices):
    SALLE_COMPLETE = "salle_complete", "Salle complète"
    HALTERES_MAISON = "halteres_maison", "Haltères maison"
    POIDS_DU_CORPS = "poids_du_corps", "Poids du corps"


# Facteurs d'activité pour le calcul du TDEE (cf. CLAUDE.md, formules métier).
FACTEURS_ACTIVITE = {
    Activite.SEDENTAIRE: 1.2,
    Activite.LEGER: 1.375,
    Activite.MODERE: 1.55,
    Activite.ACTIF: 1.725,
    Activite.TRES_ACTIF: 1.9,
}


class Profile(models.Model):
    """Profil sportif de l'utilisateur (renseigné à l'onboarding)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="utilisateur",
    )
    sexe = models.CharField("sexe", max_length=1, choices=Sexe.choices)
    date_naissance = models.DateField("date de naissance")
    taille_cm = models.PositiveSmallIntegerField("taille (cm)")
    poids_kg = models.DecimalField("poids (kg)", max_digits=5, decimal_places=2)

    niveau = models.CharField(
        "niveau", max_length=20, choices=Niveau.choices, default=Niveau.DEBUTANT
    )
    objectif = models.CharField("objectif", max_length=20, choices=Objectif.choices)
    activite = models.CharField(
        "activité", max_length=20, choices=Activite.choices, default=Activite.MODERE
    )
    jours_entrainement_par_semaine = models.PositiveSmallIntegerField(
        "jours d'entraînement / semaine", default=4
    )
    materiel = models.CharField(
        "matériel disponible",
        max_length=20,
        choices=Materiel.choices,
        default=Materiel.SALLE_COMPLETE,
    )

    blessures_limitations = models.TextField(
        "blessures / limitations", blank=True
    )
    allergies_alimentaires = models.TextField("allergies alimentaires", blank=True)
    preferences_alimentaires = models.TextField(
        "préférences alimentaires",
        blank=True,
        help_text="ex: halal, végétarien, sans porc",
    )

    cree_le = models.DateTimeField("créé le", auto_now_add=True)
    modifie_le = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "profil"
        verbose_name_plural = "profils"

    def __str__(self) -> str:
        return f"Profil de {self.user}"
