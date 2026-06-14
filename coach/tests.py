"""Tests du service de génération de programme (coach)."""

import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.models import Activite, Materiel, Niveau, Objectif, Sexe
from accounts.models import Profile
from coach import services
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
