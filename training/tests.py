"""Tests de la logique de séance et de progression (training)."""

import datetime
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from tracking.models import SetLog, WorkoutLog

from . import services
from .models import (
    Exercise,
    GroupeMusculaire,
    Program,
    ProgressionType,
    Split,
    TypeExercice,
    WorkoutDay,
    WorkoutExercise,
)

User = get_user_model()


class RepsMaxTests(SimpleTestCase):
    def test_fourchette(self):
        self.assertEqual(services.reps_max("8-12"), 12)

    def test_valeur_unique(self):
        self.assertEqual(services.reps_max("10"), 10)

    def test_aucun_nombre(self):
        self.assertIsNone(services.reps_max("AMRAP"))


class IncrementChargeTests(SimpleTestCase):
    def test_haut_du_corps(self):
        self.assertEqual(services.increment_charge(GroupeMusculaire.PECTORAUX), Decimal("2.5"))

    def test_bas_du_corps(self):
        self.assertEqual(services.increment_charge(GroupeMusculaire.JAMBES), Decimal("5"))


class SuggestionChargeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ahmed", password="x")
        self.program = Program.objects.create(
            user=self.user,
            nom="Prog",
            objectif="prise_de_masse",
            date_debut=datetime.date.today(),
            split=Split.HALF_BODY,
        )
        self.day = WorkoutDay.objects.create(program=self.program, jour_numero=1, nom="Haut")
        self.exo = Exercise.objects.create(
            nom="Développé couché", groupe_musculaire=GroupeMusculaire.PECTORAUX,
            type=TypeExercice.COMPOSE,
        )
        self.we = WorkoutExercise.objects.create(
            workout_day=self.day, exercise=self.exo, series=3,
            repetitions="8-12", temps_repos_secondes=120,
            progression_type=ProgressionType.DOUBLE_PROGRESSION,
        )

    def _log_seance(self, jour, reps_par_serie, charge):
        log = WorkoutLog.objects.create(user=self.user, workout_day=self.day, date=jour)
        for i, reps in enumerate(reps_par_serie, start=1):
            SetLog.objects.create(
                workout_log=log, workout_exercise=self.we, serie_numero=i,
                repetitions_faites=reps, charge_kg=Decimal(charge),
            )
        return log

    def test_aucun_historique(self):
        self.assertIsNone(services.suggestion_charge(self.we, self.user))

    def test_progression_si_haut_de_fourchette_atteint(self):
        # Toutes les séries à 12 reps (haut de "8-12") → +2,5 kg (haut du corps).
        self._log_seance(datetime.date(2026, 6, 1), [12, 12, 12], "60")
        self.assertEqual(services.suggestion_charge(self.we, self.user), Decimal("62.5"))

    def test_pas_de_progression_si_fourchette_non_atteinte(self):
        self._log_seance(datetime.date(2026, 6, 1), [12, 10, 8], "60")
        self.assertEqual(services.suggestion_charge(self.we, self.user), Decimal("60"))

    def test_utilise_la_derniere_seance(self):
        self._log_seance(datetime.date(2026, 6, 1), [12, 12, 12], "60")
        self._log_seance(datetime.date(2026, 6, 8), [10, 9, 8], "65")
        # La dernière séance (65 kg, fourchette non atteinte) prime.
        self.assertEqual(services.suggestion_charge(self.we, self.user), Decimal("65"))


class SeanceViewTests(TestCase):
    def setUp(self):
        from accounts.models import Objectif, Profile

        self.user = User.objects.create_user("ahmed", password="x")
        # Profil requis : le middleware d'onboarding garde sinon toutes les pages.
        Profile.objects.create(
            user=self.user, sexe="H", date_naissance=datetime.date(2000, 1, 1),
            taille_cm=180, poids_kg=Decimal("80"), objectif=Objectif.MAINTIEN,
        )
        self.client.force_login(self.user)
        self.program = Program.objects.create(
            user=self.user, nom="Prog", objectif="prise_de_masse",
            date_debut=datetime.date.today(), split=Split.HALF_BODY,
        )
        self.day = WorkoutDay.objects.create(program=self.program, jour_numero=1, nom="Haut")
        self.exo = Exercise.objects.create(
            nom="Développé couché", groupe_musculaire=GroupeMusculaire.PECTORAUX,
            type=TypeExercice.COMPOSE,
        )
        self.we = WorkoutExercise.objects.create(
            workout_day=self.day, exercise=self.exo, series=3,
            repetitions="8-12", temps_repos_secondes=120,
        )

    def test_seance_cree_le_log_du_jour(self):
        resp = self.client.get(reverse("training:seance", args=[self.day.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            WorkoutLog.objects.filter(user=self.user, workout_day=self.day).exists()
        )

    def test_enregistrer_serie(self):
        log = services.get_or_create_seance_du_jour(self.user, self.day)
        resp = self.client.post(
            reverse("training:enregistrer_serie"),
            data=json.dumps({
                "logId": log.id, "weId": self.we.id, "serie": 1,
                "reps": 10, "charge": 62.5,
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        setlog = SetLog.objects.get(workout_log=log, workout_exercise=self.we, serie_numero=1)
        self.assertEqual(setlog.repetitions_faites, 10)
        self.assertEqual(setlog.charge_kg, Decimal("62.5"))

    def test_enregistrer_serie_met_a_jour(self):
        log = services.get_or_create_seance_du_jour(self.user, self.day)
        payload = {"logId": log.id, "weId": self.we.id, "serie": 1, "reps": 10, "charge": 60}
        self.client.post(reverse("training:enregistrer_serie"),
                         data=json.dumps(payload), content_type="application/json")
        payload["reps"] = 12
        self.client.post(reverse("training:enregistrer_serie"),
                         data=json.dumps(payload), content_type="application/json")
        # Pas de doublon : la série est mise à jour.
        self.assertEqual(SetLog.objects.filter(workout_log=log, serie_numero=1).count(), 1)
        self.assertEqual(SetLog.objects.get(workout_log=log, serie_numero=1).repetitions_faites, 12)

    def test_enregistrer_serie_donnees_invalides(self):
        log = services.get_or_create_seance_du_jour(self.user, self.day)
        resp = self.client.post(
            reverse("training:enregistrer_serie"),
            data=json.dumps({"logId": log.id, "weId": self.we.id, "serie": 1, "reps": "x", "charge": 60}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_terminer_seance(self):
        log = services.get_or_create_seance_du_jour(self.user, self.day)
        resp = self.client.post(
            reverse("training:terminer_seance", args=[log.id]),
            data={"duree_minutes": "55", "ressenti": "4", "notes": "Bonne séance"},
        )
        self.assertRedirects(resp, reverse("training:programme"))
        log.refresh_from_db()
        self.assertEqual(log.duree_minutes, 55)
        self.assertEqual(log.ressenti, 4)

    def test_seance_autre_user_interdite(self):
        from accounts.models import Objectif, Profile

        autre = User.objects.create_user("autre", password="x")
        Profile.objects.create(
            user=autre, sexe="H", date_naissance=datetime.date(2000, 1, 1),
            taille_cm=180, poids_kg=Decimal("80"), objectif=Objectif.MAINTIEN,
        )
        self.client.force_login(autre)
        resp = self.client.get(reverse("training:seance", args=[self.day.id]))
        self.assertEqual(resp.status_code, 404)

    def test_seance_data_inclut_le_guide(self):
        self.exo.consignes_securite = "Garde le dos droit."
        self.exo.muscles_secondaires = "triceps"
        self.exo.save()
        resp = self.client.get(reverse("training:seance", args=[self.day.id]))
        guide = resp.context["seance_data"]["exercices"][0]["guide"]
        self.assertTrue(guide["aGuide"])
        self.assertEqual(guide["securite"], "Garde le dos droit.")
        self.assertEqual(guide["musclePrimaire"], "Pectoraux")
        self.assertEqual(guide["musclesSecondaires"], "triceps")

    def test_seance_data_guide_vide_si_rien(self):
        # description_technique vide + aucun champ guide → aGuide False.
        guide = (
            self.client.get(reverse("training:seance", args=[self.day.id]))
            .context["seance_data"]["exercices"][0]["guide"]
        )
        self.assertFalse(guide["aGuide"])


class RechercherExercicesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from accounts.models import Materiel, Niveau

        cls.dev = Exercise.objects.create(
            nom="Développé couché", nom_en="Bench press",
            groupe_musculaire=GroupeMusculaire.PECTORAUX, type=TypeExercice.COMPOSE,
            materiel_requis=Materiel.SALLE_COMPLETE, niveau_minimum=Niveau.DEBUTANT,
        )
        cls.pompes = Exercise.objects.create(
            nom="Pompes", nom_en="Push-up",
            groupe_musculaire=GroupeMusculaire.PECTORAUX, type=TypeExercice.COMPOSE,
            materiel_requis=Materiel.POIDS_DU_CORPS, niveau_minimum=Niveau.DEBUTANT,
        )
        cls.squat = Exercise.objects.create(
            nom="Squat", nom_en="Back squat",
            groupe_musculaire=GroupeMusculaire.JAMBES, type=TypeExercice.COMPOSE,
            materiel_requis=Materiel.SALLE_COMPLETE, niveau_minimum=Niveau.INTERMEDIAIRE,
        )

    def test_sans_filtre_retourne_tout_trie(self):
        res = list(services.rechercher_exercices())
        self.assertEqual(len(res), 3)
        # Tri groupe_musculaire puis nom : jambes < pectoraux.
        self.assertEqual(res[0], self.squat)

    def test_filtre_groupe(self):
        res = list(services.rechercher_exercices(groupe=GroupeMusculaire.PECTORAUX))
        self.assertCountEqual(res, [self.dev, self.pompes])

    def test_filtre_materiel(self):
        from accounts.models import Materiel

        res = list(services.rechercher_exercices(materiel=Materiel.POIDS_DU_CORPS))
        self.assertEqual(res, [self.pompes])

    def test_filtre_niveau(self):
        from accounts.models import Niveau

        res = list(services.rechercher_exercices(niveau=Niveau.INTERMEDIAIRE))
        self.assertEqual(res, [self.squat])

    def test_filtres_combines(self):
        from accounts.models import Materiel

        res = list(services.rechercher_exercices(
            groupe=GroupeMusculaire.PECTORAUX, materiel=Materiel.SALLE_COMPLETE
        ))
        self.assertEqual(res, [self.dev])

    def test_recherche_texte_fr(self):
        res = list(services.rechercher_exercices(query="pompes"))
        self.assertEqual(res, [self.pompes])

    def test_recherche_texte_en(self):
        res = list(services.rechercher_exercices(query="squat"))  # "Back squat" en EN
        self.assertEqual(res, [self.squat])

    def test_recherche_insensible_casse(self):
        res = list(services.rechercher_exercices(query="DÉVELOPPÉ"))
        self.assertEqual(res, [self.dev])

    def test_aucun_resultat(self):
        self.assertEqual(list(services.rechercher_exercices(query="inexistant")), [])


class ExerciceDetailTests(TestCase):
    def test_trouve(self):
        ex = Exercise.objects.create(
            nom="Curl", groupe_musculaire=GroupeMusculaire.BICEPS, type=TypeExercice.ISOLATION,
        )
        self.assertEqual(services.exercice_detail(ex.id), ex)

    def test_introuvable(self):
        self.assertIsNone(services.exercice_detail(999999))


class ValiderExercicesActionTests(TestCase):
    """Action admin groupée « Valider les exercices sélectionnés »."""

    def setUp(self):
        from django.contrib.admin.sites import AdminSite

        from .admin import ExerciseAdmin

        self.admin = ExerciseAdmin(Exercise, AdminSite())
        self.ia1 = Exercise.objects.create(
            nom="Exo IA 1", groupe_musculaire=GroupeMusculaire.EPAULES,
            type=TypeExercice.ISOLATION, a_valider=True,
        )
        self.ia2 = Exercise.objects.create(
            nom="Exo IA 2", groupe_musculaire=GroupeMusculaire.DOS,
            type=TypeExercice.COMPOSE, a_valider=True,
        )

    def test_action_passe_a_valider_a_false(self):
        request = mock.Mock()
        self.admin.valider_exercices(request, Exercise.objects.filter(a_valider=True))
        self.ia1.refresh_from_db()
        self.ia2.refresh_from_db()
        self.assertFalse(self.ia1.a_valider)
        self.assertFalse(self.ia2.a_valider)


class ValiderGuidesActionTests(TestCase):
    """Action admin groupée « Valider les guides générés par l'IA »."""

    def setUp(self):
        from django.contrib.admin.sites import AdminSite

        from .admin import ExerciseAdmin

        self.admin = ExerciseAdmin(Exercise, AdminSite())
        self.ex = Exercise.objects.create(
            nom="Squat", groupe_musculaire=GroupeMusculaire.JAMBES,
            type=TypeExercice.COMPOSE, consignes_securite="Dos gainé.",
            guide_a_valider=True,
        )

    def test_action_passe_guide_a_valider_a_false(self):
        self.admin.valider_guides(mock.Mock(), Exercise.objects.filter(guide_a_valider=True))
        self.ex.refresh_from_db()
        self.assertFalse(self.ex.guide_a_valider)


class FicheExerciceGuideTests(TestCase):
    """La fiche bibliothèque affiche les sections guide seulement si remplies."""

    def setUp(self):
        from accounts.models import Objectif, Profile

        self.user = User.objects.create_user("ahmed", password="x")
        Profile.objects.create(
            user=self.user, sexe="H", date_naissance=datetime.date(2000, 1, 1),
            taille_cm=180, poids_kg=Decimal("80"), objectif=Objectif.MAINTIEN,
        )
        self.client.force_login(self.user)

    def test_sections_affichees_si_remplies(self):
        ex = Exercise.objects.create(
            nom="Squat barre", groupe_musculaire=GroupeMusculaire.JAMBES,
            type=TypeExercice.COMPOSE,
            consignes_securite="Garde le dos gainé.",
            erreurs_frequentes="Talons qui décollent.",
            muscles_secondaires="ischio-jambiers, fessiers",
        )
        resp = self.client.get(reverse("training:exercice", args=[ex.id]))
        self.assertContains(resp, "Sécurité")
        self.assertContains(resp, "Garde le dos gainé.")
        self.assertContains(resp, "Erreurs fréquentes")
        self.assertContains(resp, "ischio-jambiers, fessiers")

    def test_sections_masquees_si_vides(self):
        ex = Exercise.objects.create(
            nom="Curl", groupe_musculaire=GroupeMusculaire.BICEPS,
            type=TypeExercice.ISOLATION,
        )
        resp = self.client.get(reverse("training:exercice", args=[ex.id]))
        self.assertNotContains(resp, "Erreurs fréquentes")
        # La carte « Muscles ciblés » reste présente (muscle primaire toujours connu).
        self.assertContains(resp, "Muscles ciblés")


class EnrichirGuidesCommandTests(TestCase):
    """Command `enrichir_guides` : idempotente, sûre sans clé, --force."""

    def setUp(self):
        self.vide = Exercise.objects.create(
            nom="Squat", groupe_musculaire=GroupeMusculaire.JAMBES, type=TypeExercice.COMPOSE,
        )
        self.rempli = Exercise.objects.create(
            nom="Curl", groupe_musculaire=GroupeMusculaire.BICEPS, type=TypeExercice.ISOLATION,
            muscles_secondaires="avant-bras",
        )

    def _run(self, **kwargs):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("enrichir_guides", stdout=out, stderr=StringIO(), **kwargs)
        return out.getvalue()

    @override_settings(ANTHROPIC_API_KEY="cle-test")
    def test_saute_les_guides_deja_remplis(self):
        with mock.patch("coach.services.generate_exercise_guide", return_value=True) as m:
            self._run()
        # Seul l'exercice au guide vide est traité (idempotence).
        m.assert_called_once()
        self.assertEqual(m.call_args.args[0], self.vide)

    @override_settings(ANTHROPIC_API_KEY="cle-test")
    def test_force_regenere_tout(self):
        with mock.patch("coach.services.generate_exercise_guide", return_value=True) as m:
            self._run(force=True)
        self.assertEqual(m.call_count, 2)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sans_cle_api_ne_fait_aucun_appel(self):
        with mock.patch("coach.services.generate_exercise_guide") as m:
            sortie = self._run()
        m.assert_not_called()
        self.assertIn("ANTHROPIC_API_KEY absente", sortie)
