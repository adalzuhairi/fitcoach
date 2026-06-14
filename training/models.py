from django.conf import settings
from django.db import models

from accounts.models import Materiel, Niveau, Objectif


class GroupeMusculaire(models.TextChoices):
    PECTORAUX = "pectoraux", "Pectoraux"
    DOS = "dos", "Dos"
    JAMBES = "jambes", "Jambes"
    EPAULES = "epaules", "Épaules"
    BICEPS = "biceps", "Biceps"
    TRICEPS = "triceps", "Triceps"
    ABDOS = "abdos", "Abdos"
    MOLLETS = "mollets", "Mollets"


class TypeExercice(models.TextChoices):
    COMPOSE = "compose", "Composé"
    ISOLATION = "isolation", "Isolation"


class Split(models.TextChoices):
    FULL_BODY = "full_body", "Full body"
    HALF_BODY = "half_body", "Half body"
    PUSH_PULL_LEGS = "push_pull_legs", "Push / Pull / Legs"
    SPLIT_CLASSIQUE = "split_classique", "Split classique"


class DureeSemaines(models.IntegerChoices):
    QUATRE = 4, "4 semaines"
    HUIT = 8, "8 semaines"
    DOUZE = 12, "12 semaines"


class ProgressionType(models.TextChoices):
    DOUBLE_PROGRESSION = "double_progression", "Double progression"
    CHARGE_LINEAIRE = "charge_lineaire", "Charge linéaire"
    RPE = "rpe", "RPE"


class Exercise(models.Model):
    """Exercice de musculation (catalogue, alimenté par fixture + IA)."""

    nom = models.CharField("nom", max_length=120, unique=True)
    nom_en = models.CharField("nom (anglais)", max_length=120, blank=True)
    groupe_musculaire = models.CharField(
        "groupe musculaire", max_length=20, choices=GroupeMusculaire.choices
    )
    type = models.CharField("type", max_length=20, choices=TypeExercice.choices)
    materiel_requis = models.CharField(
        "matériel requis",
        max_length=20,
        choices=Materiel.choices,
        default=Materiel.SALLE_COMPLETE,
    )
    niveau_minimum = models.CharField(
        "niveau minimum",
        max_length=20,
        choices=Niveau.choices,
        default=Niveau.DEBUTANT,
    )
    description_technique = models.TextField("description technique", blank=True)
    video_url = models.URLField("URL vidéo", blank=True)
    # Exercice créé automatiquement par l'IA, à valider par un admin.
    a_valider = models.BooleanField("à valider", default=False)

    class Meta:
        verbose_name = "exercice"
        verbose_name_plural = "exercices"
        ordering = ["groupe_musculaire", "nom"]

    def __str__(self) -> str:
        return self.nom


class Program(models.Model):
    """Programme d'entraînement d'un utilisateur."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="programs",
        verbose_name="utilisateur",
    )
    nom = models.CharField("nom", max_length=150)
    objectif = models.CharField("objectif", max_length=20, choices=Objectif.choices)
    date_debut = models.DateField("date de début")
    duree_semaines = models.PositiveSmallIntegerField(
        "durée (semaines)", choices=DureeSemaines.choices, default=DureeSemaines.HUIT
    )
    split = models.CharField("split", max_length=20, choices=Split.choices)
    actif = models.BooleanField("actif", default=True)
    genere_par_ia = models.BooleanField("généré par IA", default=False)
    # Traçabilité des appels IA (cf. coach/services.py).
    prompt_ia = models.TextField("prompt IA", blank=True)
    reponse_ia = models.JSONField("réponse IA", null=True, blank=True)

    cree_le = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "programme"
        verbose_name_plural = "programmes"
        ordering = ["-cree_le"]

    def __str__(self) -> str:
        return f"{self.nom} ({self.user})"


class WorkoutDay(models.Model):
    """Journée d'entraînement au sein d'un programme."""

    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="workout_days",
        verbose_name="programme",
    )
    jour_numero = models.PositiveSmallIntegerField("numéro de jour")
    nom = models.CharField(
        "nom", max_length=150, help_text="ex: Push — Pectoraux/Épaules/Triceps"
    )

    class Meta:
        verbose_name = "journée d'entraînement"
        verbose_name_plural = "journées d'entraînement"
        ordering = ["program", "jour_numero"]
        unique_together = [("program", "jour_numero")]

    def __str__(self) -> str:
        return f"J{self.jour_numero} — {self.nom}"


class WorkoutExercise(models.Model):
    """Exercice planifié dans une journée d'entraînement."""

    workout_day = models.ForeignKey(
        WorkoutDay,
        on_delete=models.CASCADE,
        related_name="exercises",
        verbose_name="journée",
    )
    exercise = models.ForeignKey(
        Exercise, on_delete=models.PROTECT, verbose_name="exercice"
    )
    ordre = models.PositiveSmallIntegerField("ordre", default=1)
    series = models.PositiveSmallIntegerField("séries")
    repetitions = models.CharField("répétitions", max_length=20, help_text="ex: 8-12")
    temps_repos_secondes = models.PositiveSmallIntegerField("temps de repos (s)")
    tempo = models.CharField(
        "tempo", max_length=20, blank=True, help_text="ex: 2-0-2"
    )
    notes = models.TextField("notes", blank=True)
    progression_type = models.CharField(
        "type de progression",
        max_length=20,
        choices=ProgressionType.choices,
        default=ProgressionType.DOUBLE_PROGRESSION,
    )

    class Meta:
        verbose_name = "exercice de séance"
        verbose_name_plural = "exercices de séance"
        ordering = ["workout_day", "ordre"]

    def __str__(self) -> str:
        return f"{self.exercise} — {self.series}x{self.repetitions}"
