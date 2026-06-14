"""Tests des formules nutritionnelles (cf. CLAUDE.md — obligatoires).

Tests DB-free : les fonctions de calcul prennent des primitives, et
l'orchestration est testée avec un stub de Profile (pas d'accès base).
"""

import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from accounts.models import Activite, Niveau, Objectif, Sexe
from nutrition import services
from nutrition.models import Recipe


class CalculerAgeTests(SimpleTestCase):
    def test_anniversaire_pas_encore_passe(self):
        age = services.calculer_age(
            datetime.date(2000, 6, 20), aujourdhui=datetime.date(2026, 6, 14)
        )
        self.assertEqual(age, 25)

    def test_anniversaire_passe(self):
        age = services.calculer_age(
            datetime.date(2000, 6, 20), aujourdhui=datetime.date(2026, 6, 21)
        )
        self.assertEqual(age, 26)

    def test_jour_anniversaire(self):
        age = services.calculer_age(
            datetime.date(2000, 6, 20), aujourdhui=datetime.date(2026, 6, 20)
        )
        self.assertEqual(age, 26)


class CalculerBmrTests(SimpleTestCase):
    def test_homme(self):
        # 10*80 + 6.25*180 - 5*25 + 5 = 1805
        self.assertEqual(services.calculer_bmr(Sexe.HOMME, 80, 180, 25), 1805)

    def test_femme(self):
        # 10*80 + 6.25*180 - 5*25 - 161 = 1639
        self.assertEqual(services.calculer_bmr(Sexe.FEMME, 80, 180, 25), 1639)


class CalculerTdeeTests(SimpleTestCase):
    def test_facteur_modere(self):
        self.assertAlmostEqual(services.calculer_tdee(1805, Activite.MODERE), 1805 * 1.55)

    def test_facteur_sedentaire(self):
        self.assertAlmostEqual(services.calculer_tdee(1805, Activite.SEDENTAIRE), 1805 * 1.2)


class CalculerCaloriesCiblesTests(SimpleTestCase):
    def test_prise_de_masse(self):
        self.assertEqual(services.calculer_calories_cibles(2800, Objectif.PRISE_DE_MASSE), 3100)

    def test_seche(self):
        self.assertEqual(services.calculer_calories_cibles(2800, Objectif.SECHE), 2350)

    def test_maintien(self):
        self.assertEqual(services.calculer_calories_cibles(2800, Objectif.MAINTIEN), 2800)

    def test_recomposition(self):
        self.assertEqual(services.calculer_calories_cibles(2800, Objectif.RECOMPOSITION), 2800)

    def test_force(self):
        self.assertEqual(services.calculer_calories_cibles(2800, Objectif.FORCE), 2950)


class CalculerMacrosTests(SimpleTestCase):
    def test_maintien(self):
        # poids 80 : prot 2.0 -> 160g (640 kcal), lip 0.8 -> 64g (576 kcal),
        # reste 2800-640-576 = 1584 -> 396g de glucides.
        macros = services.calculer_macros(2800, 80, Objectif.MAINTIEN)
        self.assertEqual(macros, {"proteines_g": 160, "glucides_g": 396, "lipides_g": 64})

    def test_seche_utilise_2_2_g_par_kg(self):
        # poids 80 : prot 2.2 -> 176g.
        macros = services.calculer_macros(2350, 80, Objectif.SECHE)
        self.assertEqual(macros["proteines_g"], 176)
        self.assertEqual(macros["lipides_g"], 64)
        self.assertEqual(macros["glucides_g"], 268)

    def test_somme_calories_coherente(self):
        macros = services.calculer_macros(2800, 80, Objectif.MAINTIEN)
        total = (
            macros["proteines_g"] * 4 + macros["glucides_g"] * 4 + macros["lipides_g"] * 9
        )
        # Tolérance liée aux arrondis en grammes.
        self.assertAlmostEqual(total, 2800, delta=5)

    def test_deficit_serre_reduit_les_lipides(self):
        # 1200 kcal, poids 80 : prot 640 + lip 0.8(576) > reste -> lipides au plancher 0.6 (48g).
        macros = services.calculer_macros(1200, 80, Objectif.MAINTIEN)
        self.assertEqual(macros["lipides_g"], 48)
        self.assertEqual(macros["glucides_g"], 32)

    def test_glucides_jamais_negatifs(self):
        # Calories très basses : glucides bornés à 0, jamais négatifs.
        macros = services.calculer_macros(1000, 80, Objectif.MAINTIEN)
        self.assertEqual(macros["glucides_g"], 0)


class RepartirRepasTests(SimpleTestCase):
    def _objectifs(self):
        return services.ObjectifsNutritionnels(
            tdee=2800, calories_cibles=2800, proteines_g=160, glucides_g=396, lipides_g=64
        )

    def test_nombre_de_repas(self):
        for n in (3, 4, 5, 6):
            self.assertEqual(len(services.repartir_repas(self._objectifs(), n)), n)

    def test_totaux_exacts(self):
        # Le dernier repas absorbe le reste : les totaux doivent être exacts.
        for n in (3, 4, 5, 6):
            repas = services.repartir_repas(self._objectifs(), n)
            self.assertEqual(sum(r["calories"] for r in repas), 2800)
            self.assertEqual(sum(r["proteines_g"] for r in repas), 160)
            self.assertEqual(sum(r["glucides_g"] for r in repas), 396)
            self.assertEqual(sum(r["lipides_g"] for r in repas), 64)

    def test_ordre_sequentiel(self):
        repas = services.repartir_repas(self._objectifs(), 4)
        self.assertEqual([r["ordre"] for r in repas], [1, 2, 3, 4])


class CalculerObjectifsNutritionnelsTests(SimpleTestCase):
    def _profile(self, **kwargs):
        defaults = dict(
            sexe=Sexe.HOMME,
            date_naissance=datetime.date(2000, 6, 20),
            taille_cm=180,
            poids_kg=80,
            niveau=Niveau.INTERMEDIAIRE,
            objectif=Objectif.MAINTIEN,
            activite=Activite.MODERE,
        )
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_orchestration_homme_maintien(self):
        profile = self._profile()
        res = services.calculer_objectifs_nutritionnels(
            profile, aujourdhui=datetime.date(2026, 6, 14)
        )
        # BMR 1805, TDEE 1805*1.55 = 2797.75 -> 2798, maintien -> calories = TDEE.
        self.assertEqual(res.tdee, 2798)
        self.assertEqual(res.calories_cibles, 2798)
        self.assertEqual(res.proteines_g, 160)
        self.assertEqual(res.lipides_g, 64)

    def test_orchestration_seche_protéines_plus_hautes(self):
        profile = self._profile(objectif=Objectif.SECHE)
        res = services.calculer_objectifs_nutritionnels(
            profile, aujourdhui=datetime.date(2026, 6, 14)
        )
        self.assertEqual(res.calories_cibles, 2798 - 450)
        self.assertEqual(res.proteines_g, 176)  # 2.2 g/kg en sèche


class PreferencesRequisesTests(SimpleTestCase):
    def _profile(self, preferences):
        return SimpleNamespace(preferences_alimentaires=preferences)

    def test_aucune_preference(self):
        self.assertEqual(services.preferences_requises(self._profile("")), set())

    def test_halal_et_vegetarien_accents(self):
        prefs = services.preferences_requises(self._profile("Halal, végétarien"))
        self.assertEqual(prefs, {"halal", "vegetarien"})

    def test_vegan_variantes(self):
        self.assertEqual(
            services.preferences_requises(self._profile("végétalien")), {"vegan"}
        )


class RecettesSuggereesTests(TestCase):
    def _recette(self, nom, tags):
        return Recipe.objects.create(
            nom=nom, calories=500, proteines_g=40, glucides_g=50, lipides_g=15, tags=tags
        )

    def _profile(self, objectif=Objectif.PRISE_DE_MASSE, preferences=""):
        return SimpleNamespace(objectif=objectif, preferences_alimentaires=preferences)

    def test_objectif_priorise(self):
        self._recette("Salade", tags=["seche"])
        cible = self._recette("Bowl protéiné", tags=["prise_de_masse"])
        suggestions = services.recettes_suggerees(self._profile())
        # La recette taguée avec l'objectif passe en tête.
        self.assertEqual(suggestions[0], cible)
        self.assertEqual(len(suggestions), 2)

    def test_preference_filtre_strictement(self):
        self._recette("Poulet", tags=["prise_de_masse"])
        veggie = self._recette("Tofu sauté", tags=["prise_de_masse", "vegetarien"])
        suggestions = services.recettes_suggerees(
            self._profile(preferences="végétarien")
        )
        self.assertEqual(suggestions, [veggie])

    def test_limite_respectee(self):
        for i in range(8):
            self._recette(f"Recette {i}", tags=["prise_de_masse"])
        self.assertEqual(len(services.recettes_suggerees(self._profile(), limit=6)), 6)

    def test_catalogue_vide(self):
        self.assertEqual(services.recettes_suggerees(self._profile()), [])
