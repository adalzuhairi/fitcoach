"""Tests de la logique de séance et de progression (training)."""

import datetime
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
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
        self.user = User.objects.create_user("ahmed", password="x")
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
        autre = User.objects.create_user("autre", password="x")
        self.client.force_login(autre)
        resp = self.client.get(reverse("training:seance", args=[self.day.id]))
        self.assertEqual(resp.status_code, 404)
