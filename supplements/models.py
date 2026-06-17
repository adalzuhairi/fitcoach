from django.db import models


class Categorie(models.TextChoices):
    PROTEINE = "proteine", "Protéine"
    CREATINE = "creatine", "Créatine"
    GAINER = "gainer", "Gainer (glucides + protéines)"
    ACIDES_AMINES = "acides_amines", "Acides aminés"
    PRE_WORKOUT = "pre_workout", "Pré-entraînement"
    VITAMINES_MINERAUX = "vitamines_mineraux", "Vitamines & minéraux"
    OMEGA3 = "omega3", "Oméga-3"
    AUTRE = "autre", "Autre"


class NiveauPreuve(models.TextChoices):
    """Niveau de preuve scientifique de l'efficacité (honnêteté > marketing)."""

    ELEVE = "eleve", "Preuves solides"
    MODERE = "modere", "Preuves modérées"
    FAIBLE = "faible", "Preuves limitées"


class Supplement(models.Model):
    """Complément alimentaire du catalogue global (géré en admin, non lié à un user).

    Comme training.Exercise : table partagée, alimentée par fixture et relue en admin.
    La recommandation par profil est calculée à la volée (cf. supplements.services).
    """

    nom = models.CharField("nom", max_length=120)
    nom_en = models.CharField("nom (EN)", max_length=120, blank=True)
    categorie = models.CharField("catégorie", max_length=20, choices=Categorie.choices)
    description = models.TextField("description", blank=True)
    benefices = models.TextField(
        "bénéfices", blank=True, help_text="Effets établis, sans promesse exagérée."
    )
    dosage_recommande = models.CharField("dosage recommandé", max_length=150, blank=True)
    moment_prise = models.CharField("moment de prise", max_length=150, blank=True)
    niveau_preuve = models.CharField(
        "niveau de preuve",
        max_length=10,
        choices=NiveauPreuve.choices,
        default=NiveauPreuve.MODERE,
    )
    contre_indications = models.TextField("contre-indications", blank=True)
    # Tags de régime alimentaire qui EXCLUENT ce complément (ex: ["vegan"] pour la whey).
    # Recoupé avec nutrition.services.preferences_requises(profile) pour filtrer la reco.
    exclu_pour = models.JSONField(
        "exclu pour (régimes)",
        default=list,
        blank=True,
        help_text='Liste de régimes incompatibles, ex: ["vegan", "vegetarien"].',
    )
    priorite = models.PositiveSmallIntegerField(
        "priorité d'affichage",
        default=100,
        help_text="Ordre dans sa catégorie (plus petit = affiché en premier).",
    )
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "complément"
        verbose_name_plural = "compléments"
        ordering = ["categorie", "priorite", "nom"]

    def __str__(self) -> str:
        return self.nom
