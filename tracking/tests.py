"""Tests des services du tableau de bord (tracking)."""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Objectif
from training.models import (
    Exercise,
    GroupeMusculaire,
    Program,
    Split,
    TypeExercice,
    WorkoutDay,
    WorkoutExercise,
)
from tracking import services
from tracking.models import BodyMeasurement, SetLog, WorkoutLog

User = get_user_model()


class TrackingTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ahmed", password="x")
        self.program = Program.objects.create(
            user=self.user,
            nom="Programme test",
            objectif=Objectif.PRISE_DE_MASSE,
            date_debut=datetime.date(2026, 6, 1),
            split=Split.PUSH_PULL_LEGS,
            actif=True,
        )
        self.j1 = WorkoutDay.objects.create(program=self.program, jour_numero=1, nom="Push")
        self.j2 = WorkoutDay.objects.create(program=self.program, jour_numero=2, nom="Pull")
        self.j3 = WorkoutDay.objects.create(program=self.program, jour_numero=3, nom="Legs")


class ProchaineSeanceTests(TrackingTestBase):
    def test_aucun_programme(self):
        self.assertIsNone(services.prochaine_seance(self.user, None))

    def test_sans_historique_renvoie_premiere_journee(self):
        self.assertEqual(services.prochaine_seance(self.user, self.program), self.j1)

    def test_apres_une_seance_renvoie_la_suivante(self):
        WorkoutLog.objects.create(
            user=self.user, workout_day=self.j1, date=datetime.date(2026, 6, 14)
        )
        self.assertEqual(services.prochaine_seance(self.user, self.program), self.j2)

    def test_rotation_cyclique(self):
        WorkoutLog.objects.create(
            user=self.user, workout_day=self.j3, date=datetime.date(2026, 6, 14)
        )
        # Après la dernière journée, on revient à la première.
        self.assertEqual(services.prochaine_seance(self.user, self.program), self.j1)

    def test_prend_la_seance_la_plus_recente(self):
        WorkoutLog.objects.create(
            user=self.user, workout_day=self.j1, date=datetime.date(2026, 6, 10)
        )
        WorkoutLog.objects.create(
            user=self.user, workout_day=self.j2, date=datetime.date(2026, 6, 14)
        )
        self.assertEqual(services.prochaine_seance(self.user, self.program), self.j3)

    def test_programme_sans_journee(self):
        vide = Program.objects.create(
            user=self.user,
            nom="Vide",
            objectif=Objectif.MAINTIEN,
            date_debut=datetime.date(2026, 6, 1),
            split=Split.FULL_BODY,
            actif=True,
        )
        self.assertIsNone(services.prochaine_seance(self.user, vide))


class PoidsActuelTests(TrackingTestBase):
    def test_sans_mesure_utilise_le_profil(self):
        profil = type("P", (), {"poids_kg": Decimal("82.5")})()
        self.assertEqual(services.poids_actuel(self.user, profil), Decimal("82.5"))

    def test_avec_mesure_prend_la_plus_recente(self):
        BodyMeasurement.objects.create(
            user=self.user, date=datetime.date(2026, 6, 1), poids_kg=Decimal("80")
        )
        BodyMeasurement.objects.create(
            user=self.user, date=datetime.date(2026, 6, 14), poids_kg=Decimal("78.4")
        )
        self.assertEqual(services.poids_actuel(self.user), Decimal("78.4"))


class HistoriquePoidsTests(TrackingTestBase):
    def test_ordre_chronologique_croissant(self):
        BodyMeasurement.objects.create(
            user=self.user, date=datetime.date(2026, 6, 14), poids_kg=Decimal("78")
        )
        BodyMeasurement.objects.create(
            user=self.user, date=datetime.date(2026, 6, 1), poids_kg=Decimal("80")
        )
        hist = services.historique_poids(self.user)
        self.assertEqual([p["date"] for p in hist], ["2026-06-01", "2026-06-14"])
        self.assertEqual(hist[0]["poids"], 80.0)

    def test_respecte_la_limite(self):
        for jour in range(1, 20):
            BodyMeasurement.objects.create(
                user=self.user,
                date=datetime.date(2026, 6, jour),
                poids_kg=Decimal("80"),
            )
        hist = services.historique_poids(self.user, limit=12)
        self.assertEqual(len(hist), 12)
        # Garde les plus récentes : la dernière date est le 19.
        self.assertEqual(hist[-1]["date"], "2026-06-19")

    def test_vide(self):
        self.assertEqual(services.historique_poids(self.user), [])


class EnregistrerMesureTests(TrackingTestBase):
    def test_poids_seul(self):
        mesure = services.enregistrer_mesure(
            self.user, {"date": datetime.date(2026, 6, 14), "poids_kg": Decimal("80.5")}
        )
        self.assertEqual(mesure.poids_kg, Decimal("80.5"))
        self.assertIsNone(mesure.tour_taille)
        self.assertEqual(BodyMeasurement.objects.filter(user=self.user).count(), 1)

    def test_avec_mensurations(self):
        mesure = services.enregistrer_mesure(
            self.user,
            {
                "date": datetime.date(2026, 6, 14),
                "poids_kg": Decimal("80"),
                "tour_taille": Decimal("82.5"),
                "tour_bras": Decimal("38"),
            },
        )
        self.assertEqual(mesure.tour_taille, Decimal("82.5"))
        self.assertEqual(mesure.tour_bras, Decimal("38"))

    def test_date_par_defaut_aujourdhui(self):
        mesure = services.enregistrer_mesure(self.user, {"poids_kg": Decimal("80")})
        self.assertEqual(mesure.date, datetime.date.today())

    def test_doublon_de_date_met_a_jour(self):
        date = datetime.date(2026, 6, 14)
        services.enregistrer_mesure(self.user, {"date": date, "poids_kg": Decimal("80")})
        services.enregistrer_mesure(self.user, {"date": date, "poids_kg": Decimal("79")})
        mesures = BodyMeasurement.objects.filter(user=self.user)
        self.assertEqual(mesures.count(), 1)
        self.assertEqual(mesures.first().poids_kg, Decimal("79"))

    def test_update_ne_efface_pas_les_champs_absents(self):
        date = datetime.date(2026, 6, 14)
        services.enregistrer_mesure(
            self.user, {"date": date, "poids_kg": Decimal("80"), "tour_bras": Decimal("38")}
        )
        # Nouvelle saisie du jour sans le tour de bras : il doit être conservé.
        services.enregistrer_mesure(self.user, {"date": date, "poids_kg": Decimal("79")})
        mesure = BodyMeasurement.objects.get(user=self.user, date=date)
        self.assertEqual(mesure.poids_kg, Decimal("79"))
        self.assertEqual(mesure.tour_bras, Decimal("38"))


class HistoriqueMesuresTests(TrackingTestBase):
    def test_ordre_et_serialisation(self):
        BodyMeasurement.objects.create(
            user=self.user, date=datetime.date(2026, 6, 14), poids_kg=Decimal("78"),
            tour_taille=Decimal("80"),
        )
        BodyMeasurement.objects.create(
            user=self.user, date=datetime.date(2026, 6, 1), poids_kg=Decimal("80"),
        )
        hist = services.historique_mesures(self.user)
        self.assertEqual([p["date"] for p in hist], ["2026-06-01", "2026-06-14"])
        # Tour absent → None ; présent → float.
        self.assertIsNone(hist[0]["tour_taille"])
        self.assertEqual(hist[1]["tour_taille"], 80.0)
        self.assertEqual(hist[0]["poids"], 80.0)

    def test_limite(self):
        for jour in range(1, 10):
            BodyMeasurement.objects.create(
                user=self.user, date=datetime.date(2026, 6, jour), poids_kg=Decimal("80")
            )
        self.assertEqual(len(services.historique_mesures(self.user, limit=5)), 5)

    def test_vide(self):
        self.assertEqual(services.historique_mesures(self.user), [])


class ProgressionTestBase(TrackingTestBase):
    """Ajoute des exercices loggés à la base commune (user + programme j1/j2/j3)."""

    def setUp(self):
        super().setUp()
        self.dev = Exercise.objects.create(
            nom="Développé couché",
            groupe_musculaire=GroupeMusculaire.PECTORAUX,
            type=TypeExercice.COMPOSE,
        )
        self.squat = Exercise.objects.create(
            nom="Squat",
            groupe_musculaire=GroupeMusculaire.JAMBES,
            type=TypeExercice.COMPOSE,
        )
        self.we_dev = WorkoutExercise.objects.create(
            workout_day=self.j1, exercise=self.dev, series=3,
            repetitions="8-12", temps_repos_secondes=120,
        )
        self.we_squat = WorkoutExercise.objects.create(
            workout_day=self.j3, exercise=self.squat, series=3,
            repetitions="5", temps_repos_secondes=180,
        )

    def _log(self, date, workout_day):
        return WorkoutLog.objects.create(user=self.user, workout_day=workout_day, date=date)

    def _set(self, log, we, numero, reps, charge):
        return SetLog.objects.create(
            workout_log=log, workout_exercise=we, serie_numero=numero,
            repetitions_faites=reps, charge_kg=Decimal(str(charge)),
        )


class ExercicesLoggesTests(ProgressionTestBase):
    def test_seuls_les_exercices_logges(self):
        log = self._log(datetime.date(2026, 6, 14), self.j1)
        self._set(log, self.we_dev, 1, 10, 60)
        exercices = services.exercices_logges(self.user)
        self.assertEqual(exercices, [self.dev])  # squat non loggé

    def test_distinct_et_trie(self):
        log1 = self._log(datetime.date(2026, 6, 1), self.j1)
        self._set(log1, self.we_dev, 1, 10, 60)
        log2 = self._log(datetime.date(2026, 6, 8), self.j1)
        self._set(log2, self.we_dev, 1, 10, 62)  # même exercice, autre séance
        log3 = self._log(datetime.date(2026, 6, 9), self.j3)
        self._set(log3, self.we_squat, 1, 5, 100)
        exercices = services.exercices_logges(self.user)
        # Tri alphabétique, sans doublon.
        self.assertEqual(exercices, [self.dev, self.squat])

    def test_vide(self):
        self.assertEqual(services.exercices_logges(self.user), [])


class ProgressionChargeTests(ProgressionTestBase):
    def test_charge_max_par_seance_chronologique(self):
        log1 = self._log(datetime.date(2026, 6, 8), self.j1)
        self._set(log1, self.we_dev, 1, 10, 60)
        self._set(log1, self.we_dev, 2, 8, 65)  # plus lourde du jour
        log2 = self._log(datetime.date(2026, 6, 1), self.j1)
        self._set(log2, self.we_dev, 1, 10, 55)
        charge = services.progression_charge(self.user, self.dev)
        self.assertEqual(
            charge,
            [
                {"date": "2026-06-01", "charge": 55.0},
                {"date": "2026-06-08", "charge": 65.0},
            ],
        )

    def test_isole_par_exercice(self):
        log = self._log(datetime.date(2026, 6, 8), self.j3)
        self._set(log, self.we_squat, 1, 5, 100)
        self.assertEqual(services.progression_charge(self.user, self.dev), [])

    def test_vide(self):
        self.assertEqual(services.progression_charge(self.user, self.dev), [])


class VolumeHebdomadaireTests(ProgressionTestBase):
    def test_agregation_par_semaine(self):
        # Mercredi de référence : lundi courant = 2026-06-15.
        aujourdhui = datetime.date(2026, 6, 17)
        log_cette_sem = self._log(datetime.date(2026, 6, 16), self.j1)
        self._set(log_cette_sem, self.we_dev, 1, 10, 100)  # 1000
        log_sem_prec = self._log(datetime.date(2026, 6, 8), self.j1)  # lundi précédent
        self._set(log_sem_prec, self.we_dev, 1, 5, 50)  # 250
        serie = services.volume_hebdomadaire(self.user, n_semaines=8, aujourdhui=aujourdhui)
        self.assertEqual(len(serie), 8)
        self.assertEqual(serie[-1], {"semaine": "2026-06-15", "volume": 1000})
        self.assertEqual(serie[-2], {"semaine": "2026-06-08", "volume": 250})
        # Les semaines sans entraînement sont à 0.
        self.assertEqual(serie[0]["volume"], 0)

    def test_somme_des_series_dans_la_semaine(self):
        aujourdhui = datetime.date(2026, 6, 17)
        log = self._log(datetime.date(2026, 6, 16), self.j1)
        self._set(log, self.we_dev, 1, 10, 100)  # 1000
        self._set(log, self.we_dev, 2, 8, 100)   # 800
        serie = services.volume_hebdomadaire(self.user, n_semaines=4, aujourdhui=aujourdhui)
        self.assertEqual(serie[-1]["volume"], 1800)

    def test_exclut_hors_fenetre(self):
        aujourdhui = datetime.date(2026, 6, 17)
        vieux = self._log(datetime.date(2026, 1, 1), self.j1)
        self._set(vieux, self.we_dev, 1, 10, 100)
        serie = services.volume_hebdomadaire(self.user, n_semaines=4, aujourdhui=aujourdhui)
        self.assertTrue(all(point["volume"] == 0 for point in serie))
