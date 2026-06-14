"""Tests d'intégration de l'onboarding (nécessitent une base de données)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from nutrition.models import NutritionPlan

from .models import Profile

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
