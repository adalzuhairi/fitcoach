from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from training.models import WorkoutDay, WorkoutExercise


class WorkoutLog(models.Model):
    """Journal d'une séance réalisée par l'utilisateur."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workout_logs",
        verbose_name="utilisateur",
    )
    workout_day = models.ForeignKey(
        WorkoutDay,
        on_delete=models.SET_NULL,
        null=True,
        related_name="logs",
        verbose_name="journée",
    )
    date = models.DateField("date")
    duree_minutes = models.PositiveSmallIntegerField("durée (min)", null=True, blank=True)
    ressenti = models.PositiveSmallIntegerField(
        "ressenti (1-5)",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    notes = models.TextField("notes", blank=True)

    class Meta:
        verbose_name = "séance réalisée"
        verbose_name_plural = "séances réalisées"
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"Séance du {self.date} ({self.user})"


class SetLog(models.Model):
    """Série réalisée pour un exercice donné lors d'une séance."""

    workout_log = models.ForeignKey(
        WorkoutLog,
        on_delete=models.CASCADE,
        related_name="set_logs",
        verbose_name="séance",
    )
    workout_exercise = models.ForeignKey(
        WorkoutExercise,
        on_delete=models.CASCADE,
        related_name="set_logs",
        verbose_name="exercice de séance",
    )
    serie_numero = models.PositiveSmallIntegerField("numéro de série")
    repetitions_faites = models.PositiveSmallIntegerField("répétitions faites")
    charge_kg = models.DecimalField("charge (kg)", max_digits=6, decimal_places=2)
    rpe = models.DecimalField(
        "RPE", max_digits=3, decimal_places=1, null=True, blank=True
    )

    class Meta:
        verbose_name = "série réalisée"
        verbose_name_plural = "séries réalisées"
        ordering = ["workout_log", "workout_exercise", "serie_numero"]

    def __str__(self) -> str:
        return f"Série {self.serie_numero} — {self.repetitions_faites}x{self.charge_kg}kg"


class SubstitutionSeance(models.Model):
    """Substitution ponctuelle d'un exercice pendant une séance (option B).

    Trace qu'un créneau du programme (`workout_exercise`) a été remplacé par un
    autre exercice (`exercise_substitut`) le temps d'UNE séance (`workout_log`).
    Le programme n'est jamais modifié : la prochaine séance repart du plan
    initial. Une seule substitution par créneau et par séance ; annuler le
    remplacement (undo) revient simplement à supprimer cette ligne.

    On trace en base plutôt que de remplacer « à l'affichage » car les `SetLog`
    pointent vers le créneau (`workout_exercise`), pas vers l'exercice : sans
    cette trace, les séries faites sur le substitut seraient comptées comme
    faites sur l'exercice du programme et fausseraient progression et
    suggestions de charge.
    """

    workout_log = models.ForeignKey(
        WorkoutLog,
        on_delete=models.CASCADE,
        related_name="substitutions",
        verbose_name="séance",
    )
    workout_exercise = models.ForeignKey(
        WorkoutExercise,
        on_delete=models.CASCADE,
        related_name="substitutions",
        verbose_name="créneau remplacé",
    )
    exercise_substitut = models.ForeignKey(
        "training.Exercise",
        on_delete=models.PROTECT,
        related_name="substitutions",
        verbose_name="exercice de remplacement",
    )
    cree_le = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "substitution de séance"
        verbose_name_plural = "substitutions de séance"
        ordering = ["-cree_le"]
        unique_together = [("workout_log", "workout_exercise")]

    def __str__(self) -> str:
        return (
            f"{self.workout_exercise.exercise} → {self.exercise_substitut} "
            f"({self.workout_log.date})"
        )


class WaterIntake(models.Model):
    """Consommation d'eau cumulée d'un utilisateur sur une journée.

    Une seule ligne par (user, date) : chaque ajout incrémente `quantite_ml`.
    La réinitialisation quotidienne est gratuite — on lit toujours la ligne du
    jour courant, celle de la veille reste à part.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="water_intakes",
        verbose_name="utilisateur",
    )
    date = models.DateField("date")
    quantite_ml = models.PositiveIntegerField("quantité bue (ml)", default=0)

    class Meta:
        verbose_name = "consommation d'eau"
        verbose_name_plural = "consommations d'eau"
        ordering = ["-date"]
        unique_together = [("user", "date")]

    def __str__(self) -> str:
        return f"{self.quantite_ml} ml le {self.date} ({self.user})"


class BodyMeasurement(models.Model):
    """Mesures corporelles d'un utilisateur à une date donnée."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="measurements",
        verbose_name="utilisateur",
    )
    date = models.DateField("date")
    poids_kg = models.DecimalField("poids (kg)", max_digits=5, decimal_places=2)
    tour_taille = models.DecimalField(
        "tour de taille (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    tour_bras = models.DecimalField(
        "tour de bras (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    tour_poitrine = models.DecimalField(
        "tour de poitrine (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    tour_cuisses = models.DecimalField(
        "tour de cuisses (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    photo = models.ImageField("photo", upload_to="mesures/", null=True, blank=True)

    class Meta:
        verbose_name = "mesure corporelle"
        verbose_name_plural = "mesures corporelles"
        ordering = ["-date"]
        unique_together = [("user", "date")]

    def __str__(self) -> str:
        return f"{self.poids_kg} kg le {self.date} ({self.user})"
