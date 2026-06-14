"""Tests du service de génération de programme (coach)."""

import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.models import Activite, Materiel, Niveau, Objectif, Sexe
from accounts.models import Profile
from coach import services
from nutrition.models import Meal, NutritionPlan, Recipe
from training.models import Exercise, Program, Split, WorkoutExercise

User = get_user_model()


def _profile(user, **kwargs):
    defaults = dict(
        user=user,
        sexe=Sexe.HOMME,
        date_naissance=datetime.date(2000, 1, 1),
        taille_cm=180,
        poids_kg=80,
        niveau=Niveau.INTERMEDIAIRE,
        objectif=Objectif.PRISE_DE_MASSE,
        activite=Activite.MODERE,
        jours_entrainement_par_semaine=4,
        materiel=Materiel.SALLE_COMPLETE,
    )
    defaults.update(kwargs)
    return Profile.objects.create(**defaults)


class GenerateProgramFallbackTests(TestCase):
    fixtures = ["exercises"]

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ahmed", password="x")

    @override_settings(ANTHROPIC_API_KEY="")
    def test_fallback_sans_cle_api(self):
        profile = _profile(self.user, jours_entrainement_par_semaine=4)
        program = services.generate_program(profile)

        self.assertFalse(program.genere_par_ia)
        self.assertEqual(program.split, Split.HALF_BODY)
        self.assertEqual(program.workout_days.count(), 4)
        self.assertTrue(program.actif)
        # Le prompt IA n'est pas stocké pour un programme de fallback.
        self.assertEqual(program.prompt_ia, "")

    @override_settings(ANTHROPIC_API_KEY="")
    def test_fallback_mappe_les_exercices_existants(self):
        profile = _profile(self.user, jours_entrainement_par_semaine=4)
        nb_exercices_avant = Exercise.objects.count()
        services.generate_program(profile)
        # Les templates utilisent des noms de la fixture : aucun exercice créé.
        self.assertEqual(Exercise.objects.count(), nb_exercices_avant)
        self.assertFalse(Exercise.objects.filter(a_valider=True).exists())

    @override_settings(ANTHROPIC_API_KEY="")
    def test_remplace_le_programme_actif(self):
        profile = _profile(self.user)
        premier = services.generate_program(profile)
        second = services.generate_program(profile)

        premier.refresh_from_db()
        self.assertFalse(premier.actif)
        self.assertTrue(second.actif)
        self.assertEqual(Program.objects.filter(user=self.user, actif=True).count(), 1)


class GenerateProgramIaTests(TestCase):
    fixtures = ["exercises"]

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ahmed", password="x")
        self.reponse_ia = {
            "split": "push_pull_legs",
            "jours": [
                {
                    "nom": "Push",
                    "exercices": [
                        {
                            "nom": "Développé couché barre",
                            "groupe_musculaire": "pectoraux",
                            "series": 4,
                            "reps": "6-10",
                            "repos_s": 150,
                            "notes": "Contrôle la descente.",
                        },
                        {
                            "nom": "Exercice Inventé Par l'IA",
                            "groupe_musculaire": "epaules",
                            "series": 3,
                            "reps": "10-12",
                            "repos_s": 90,
                            "notes": "",
                        },
                    ],
                }
            ],
        }

    @override_settings(ANTHROPIC_API_KEY="cle-test")
    def test_chemin_ia_stocke_prompt_et_reponse(self):
        with mock.patch.object(services, "_call_claude", return_value=self.reponse_ia) as m:
            profile = _profile(self.user)
            program = services.generate_program(profile)

        m.assert_called_once()
        self.assertTrue(program.genere_par_ia)
        self.assertNotEqual(program.prompt_ia, "")
        self.assertEqual(program.reponse_ia, self.reponse_ia)
        self.assertEqual(program.split, Split.PUSH_PULL_LEGS)

    @override_settings(ANTHROPIC_API_KEY="cle-test")
    def test_exercice_absent_est_cree_a_valider(self):
        with mock.patch.object(services, "_call_claude", return_value=self.reponse_ia):
            profile = _profile(self.user)
            services.generate_program(profile)

        invente = Exercise.objects.get(nom="Exercice Inventé Par l'IA")
        self.assertTrue(invente.a_valider)
        self.assertEqual(invente.groupe_musculaire, "epaules")
        self.assertEqual(invente.materiel_requis, Materiel.SALLE_COMPLETE)

    @override_settings(ANTHROPIC_API_KEY="cle-test")
    def test_fallback_si_appel_ia_echoue(self):
        # Si l'appel Claude lève, on bascule sur les templates (genere_par_ia=False).
        with mock.patch.object(services, "_call_claude", side_effect=RuntimeError("boom")):
            profile = _profile(self.user, jours_entrainement_par_semaine=4)
            program = services.generate_program(profile)

        self.assertFalse(program.genere_par_ia)
        self.assertEqual(program.split, Split.HALF_BODY)

    @override_settings(ANTHROPIC_API_KEY="cle-test")
    def test_reps_converties_en_chaine(self):
        with mock.patch.object(services, "_call_claude", return_value=self.reponse_ia):
            profile = _profile(self.user)
            services.generate_program(profile)
        we = WorkoutExercise.objects.get(exercise__nom="Développé couché barre")
        self.assertEqual(we.repetitions, "6-10")
        self.assertEqual(we.temps_repos_secondes, 150)


def _recette(nom, **kw):
    base = dict(
        nom=nom,
        description="desc",
        instructions="1. étape",
        temps_preparation_min=15,
        portions=1,
        calories=500,
        proteines_g=40,
        glucides_g=50,
        lipides_g=15,
        ingredients=[{"nom": "Poulet", "quantite": "150", "unite": "g"}],
        tags=["rapide", "halal"],
    )
    base.update(kw)
    return base


class GenerateRecipesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ahmed", password="x")
        self.profile = _profile(
            self.user,
            allergies_alimentaires="arachides, lactose",
            preferences_alimentaires="halal, sans porc",
        )
        plan = NutritionPlan.objects.create(
            user=self.user, tdee_calcule=2500, calories_cibles=2800,
            proteines_g=160, glucides_g=350, lipides_g=80, nombre_repas=4,
        )
        self.meal = Meal.objects.create(
            plan=plan, nom="Déjeuner", ordre=2,
            calories=700, proteines_g=45, glucides_g=80, lipides_g=20,
        )
        self.reponse = {"recettes": [_recette("Poulet riz"), _recette("Bowl thon"), _recette("Omelette")]}

    @override_settings(ANTHROPIC_API_KEY="cle-test")
    def test_json_valide_cree_recipes(self):
        with mock.patch.object(services, "_call_claude_recipes", return_value=self.reponse) as m:
            recettes = services.generate_recipes(self.profile, self.meal, n=3)

        m.assert_called_once()
        self.assertEqual(len(recettes), 3)
        self.assertEqual(Recipe.objects.filter(generee_par_ia=True).count(), 3)
        self.assertTrue(all(r.generee_par_ia for r in recettes))

    @override_settings(ANTHROPIC_API_KEY="cle-test")
    def test_json_invalide_bascule_sur_fallback(self):
        # Une erreur de parsing/appel doit basculer sur les recettes de repli.
        with mock.patch.object(services, "_call_claude_recipes", side_effect=ValueError("bad json")):
            recettes = services.generate_recipes(self.profile, self.meal, n=3)

        self.assertEqual(len(recettes), 3)
        self.assertTrue(all(not r.generee_par_ia for r in recettes))

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sans_cle_api_utilise_fallback(self):
        with mock.patch.object(services, "_call_claude_recipes") as m:
            recettes = services.generate_recipes(self.profile, self.meal, n=2)

        m.assert_not_called()
        self.assertEqual(len(recettes), 2)
        self.assertTrue(all(not r.generee_par_ia for r in recettes))

    def test_prompt_contient_allergies_et_preferences(self):
        prompt = services._build_recipe_prompt(self.profile, self.meal, 3)
        self.assertIn("arachides", prompt)
        self.assertIn("lactose", prompt)
        self.assertIn("halal", prompt)
        # Macros cibles du repas présentes dans le prompt.
        self.assertIn("700", prompt)
        self.assertIn("45", prompt)

    @override_settings(ANTHROPIC_API_KEY="cle-test")
    def test_cache_evite_un_second_appel_api(self):
        with mock.patch.object(services, "_call_claude_recipes", return_value=self.reponse) as m:
            services.generate_recipes(self.profile, self.meal, n=3)
            recettes2 = services.generate_recipes(self.profile, self.meal, n=3)

        # Deuxième appel servi par le cache : l'API n'est appelée qu'une fois.
        m.assert_called_once()
        self.assertEqual(len(recettes2), 3)
        # Dédoublonnage par nom : pas de duplication en base.
        self.assertEqual(Recipe.objects.count(), 3)
