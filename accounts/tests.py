"""Tests d'intégration de l'onboarding (nécessitent une base de données)."""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from nutrition.models import Meal, NutritionPlan
from tracking.models import BodyMeasurement
from training.models import Program, Split, WorkoutDay

from .models import Objectif, Profile

User = get_user_model()


class OnboardingViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ahmed", password="motdepasse123")
        self.client.force_login(self.user)
        self.donnees = {
            "sexe": "H",
            "date_naissance": "2000-06-20",
            "taille_cm": "180",
            "poids_kg": "80",
            "objectif": "maintien",
            "niveau": "intermediaire",
            "activite": "modere",
            "jours_entrainement_par_semaine": "4",
            "materiel": "salle_complete",
            "nombre_repas": "4",
            "preferences_alimentaires": "halal",
            "allergies_alimentaires": "",
            "blessures_limitations": "",
        }

    def test_get_affiche_le_formulaire(self):
        response = self.client.get(reverse("accounts:onboarding"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/onboarding.html")

    def test_post_cree_profil_et_plan(self):
        response = self.client.post(reverse("accounts:onboarding"), self.donnees)
        self.assertRedirects(response, reverse("accounts:profil"))

        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.objectif, "maintien")

        plan = NutritionPlan.objects.get(user=self.user, actif=True)
        self.assertEqual(plan.nombre_repas, 4)
        self.assertEqual(plan.meals.count(), 4)
        # Cohérence : la somme des repas correspond au plan.
        self.assertEqual(
            sum(m.calories for m in plan.meals.all()), plan.calories_cibles
        )

    def test_post_invalide_renvoie_le_formulaire(self):
        donnees = dict(self.donnees, jours_entrainement_par_semaine="9")
        response = self.client.post(reverse("accounts:onboarding"), donnees)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Profile.objects.filter(user=self.user).exists())

    def test_reonboarding_remplace_le_plan_actif(self):
        self.client.post(reverse("accounts:onboarding"), self.donnees)
        # Deuxième passage : objectif sèche -> nouveau plan, l'ancien devient inactif.
        self.client.post(reverse("accounts:onboarding"), dict(self.donnees, objectif="seche"))

        self.assertEqual(Profile.objects.filter(user=self.user).count(), 1)
        self.assertEqual(NutritionPlan.objects.filter(user=self.user, actif=True).count(), 1)
        self.assertEqual(NutritionPlan.objects.filter(user=self.user).count(), 2)

    def test_onboarding_exige_connexion(self):
        self.client.logout()
        response = self.client.get(reverse("accounts:onboarding"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_profil_sans_profil_redirige_vers_onboarding(self):
        response = self.client.get(reverse("accounts:profil"))
        self.assertRedirects(response, reverse("accounts:onboarding"))


class IsolationInterUtilisateursTests(TestCase):
    """Audit : un utilisateur ne doit jamais accéder aux données d'un autre."""

    def setUp(self):
        # Alice possède toutes les données ; Bob est l'intrus connecté.
        self.alice = User.objects.create_user(username="alice", password="x")
        self.bob = User.objects.create_user(username="bob", password="x")

        self.program = Program.objects.create(
            user=self.alice, nom="Prog Alice", objectif=Objectif.PRISE_DE_MASSE,
            date_debut=datetime.date(2026, 6, 1), split=Split.FULL_BODY, actif=True,
        )
        self.day = WorkoutDay.objects.create(program=self.program, jour_numero=1, nom="J1")

        self.mesure = BodyMeasurement.objects.create(
            user=self.alice, date=datetime.date(2026, 6, 10), poids_kg=Decimal("80"),
        )

        plan = NutritionPlan.objects.create(
            user=self.alice, tdee_calcule=2500, calories_cibles=2800,
            proteines_g=160, glucides_g=350, lipides_g=80, nombre_repas=4,
        )
        self.meal = Meal.objects.create(
            plan=plan, nom="Déjeuner", ordre=1,
            calories=700, proteines_g=45, glucides_g=80, lipides_g=20,
        )

        self.client.force_login(self.bob)

    def test_bob_ne_voit_pas_la_seance_d_alice(self):
        r = self.client.get(reverse("training:seance", args=[self.day.id]))
        self.assertEqual(r.status_code, 404)

    def test_bob_ne_peut_pas_modifier_la_mesure_d_alice(self):
        r = self.client.get(reverse("tracking:modifier_mesure", args=[self.mesure.id]))
        self.assertEqual(r.status_code, 404)

    def test_bob_ne_peut_pas_supprimer_la_mesure_d_alice(self):
        r = self.client.post(reverse("tracking:supprimer_mesure", args=[self.mesure.id]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(BodyMeasurement.objects.filter(id=self.mesure.id).exists())

    def test_bob_ne_voit_pas_les_recettes_du_repas_d_alice(self):
        r = self.client.get(reverse("nutrition:recettes_repas", args=[self.meal.id]))
        self.assertEqual(r.status_code, 404)

    def test_bob_ne_peut_pas_generer_sur_le_repas_d_alice(self):
        r = self.client.post(reverse("nutrition:generer_recettes", args=[self.meal.id]))
        self.assertEqual(r.status_code, 404)

    def test_bob_n_a_pas_de_programme_actif(self):
        # Le programme d'Alice ne doit pas fuiter : Bob est renvoyé vers l'onboarding.
        r = self.client.get(reverse("training:programme"))
        self.assertRedirects(r, reverse("accounts:onboarding"))

    def test_mesures_scopees_par_utilisateur(self):
        # La liste des mesures de Bob ne contient pas celles d'Alice.
        r = self.client.get(reverse("tracking:mesures"))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.mesure, list(r.context["mesures"]))


class LandingTests(TestCase):
    """Racine publique : landing pour les visiteurs, dashboard si connecté."""

    def test_visiteur_voit_la_landing(self):
        r = self.client.get(reverse("landing"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "landing.html")

    def test_utilisateur_connecte_redirige_vers_dashboard(self):
        user = User.objects.create_user(username="ahmed", password="x")
        self.client.force_login(user)
        r = self.client.get(reverse("landing"))
        self.assertRedirects(r, reverse("tracking:dashboard"), target_status_code=302)


class AccesAnonymeTests(TestCase):
    """Les pages de données exigent une connexion (redirection vers le login)."""

    def test_pages_protegees_redirigent_vers_login(self):
        for nom in [
            "tracking:dashboard",
            "training:programme",
            "nutrition:ma_nutrition",
            "tracking:mesures",
            "tracking:progression",
        ]:
            r = self.client.get(reverse(nom))
            self.assertEqual(r.status_code, 302, nom)
            self.assertIn("/accounts/login/", r.url, nom)
