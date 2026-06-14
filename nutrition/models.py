from django.conf import settings
from django.db import models


class NutritionPlan(models.Model):
    """Plan nutritionnel calculé pour un utilisateur (TDEE, macros cibles)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="nutrition_plans",
        verbose_name="utilisateur",
    )
    date_creation = models.DateTimeField("date de création", auto_now_add=True)
    actif = models.BooleanField("actif", default=True)

    tdee_calcule = models.PositiveIntegerField("TDEE calculé (kcal)")
    calories_cibles = models.PositiveIntegerField("calories cibles (kcal)")
    proteines_g = models.PositiveSmallIntegerField("protéines (g)")
    glucides_g = models.PositiveSmallIntegerField("glucides (g)")
    lipides_g = models.PositiveSmallIntegerField("lipides (g)")
    nombre_repas = models.PositiveSmallIntegerField("nombre de repas", default=4)

    class Meta:
        verbose_name = "plan nutritionnel"
        verbose_name_plural = "plans nutritionnels"
        ordering = ["-date_creation"]

    def __str__(self) -> str:
        return f"Plan {self.calories_cibles} kcal ({self.user})"


class Meal(models.Model):
    """Répartition d'un repas au sein d'un plan nutritionnel."""

    plan = models.ForeignKey(
        NutritionPlan,
        on_delete=models.CASCADE,
        related_name="meals",
        verbose_name="plan",
    )
    nom = models.CharField(
        "nom", max_length=50, help_text="ex: petit-déj, déjeuner, collation, dîner"
    )
    ordre = models.PositiveSmallIntegerField("ordre", default=1)
    calories = models.PositiveIntegerField("calories (kcal)")
    proteines_g = models.PositiveSmallIntegerField("protéines (g)")
    glucides_g = models.PositiveSmallIntegerField("glucides (g)")
    lipides_g = models.PositiveSmallIntegerField("lipides (g)")

    class Meta:
        verbose_name = "repas"
        verbose_name_plural = "repas"
        ordering = ["plan", "ordre"]

    def __str__(self) -> str:
        return f"{self.nom} ({self.calories} kcal)"


class Recipe(models.Model):
    """Recette privée d'un utilisateur (génération IA), valeurs nutritionnelles par portion.

    Chaque recette appartient à un utilisateur : générée selon ses macros, allergies
    et préférences, elle ne doit pas être visible par les autres (confidentialité +
    pertinence). La bibliothèque d'exercices (Exercise) reste, elle, globale.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recipes",
        verbose_name="utilisateur",
    )
    nom = models.CharField("nom", max_length=150)
    description = models.TextField("description", blank=True)
    instructions = models.TextField("instructions", blank=True)
    temps_preparation_min = models.PositiveSmallIntegerField(
        "temps de préparation (min)", default=0
    )
    portions = models.PositiveSmallIntegerField("portions", default=1)

    calories = models.PositiveIntegerField("calories / portion (kcal)")
    proteines_g = models.PositiveSmallIntegerField("protéines / portion (g)")
    glucides_g = models.PositiveSmallIntegerField("glucides / portion (g)")
    lipides_g = models.PositiveSmallIntegerField("lipides / portion (g)")

    # Liste d'ingrédients : [{"nom": ..., "quantite": ..., "unite": ...}, ...]
    ingredients = models.JSONField("ingrédients", default=list, blank=True)
    # Tags libres : prise_de_masse, seche, rapide, batch_cooking, halal, etc.
    tags = models.JSONField("tags", default=list, blank=True)
    generee_par_ia = models.BooleanField("générée par IA", default=False)

    cree_le = models.DateTimeField("créée le", auto_now_add=True)

    class Meta:
        verbose_name = "recette"
        verbose_name_plural = "recettes"
        ordering = ["nom"]

    def __str__(self) -> str:
        return self.nom
