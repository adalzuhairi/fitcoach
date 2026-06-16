"""Tests des services du tableau de bord (tracking)."""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Objectif, Profile
from django.urls import reverse
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
from tracking.models import BodyMeasurement, SetLog, WaterIntake, WorkoutLog

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


class EtapesDemarrageTests(TrackingTestBase):
    """La checklist de démarrage reflète l'état réel du compte."""

    def _etat(self):
        return {e["cle"]: e["done"] for e in services.etapes_demarrage(self.user)["etapes"]}

    def test_sans_rien_seance_et_pesee_non_faites(self):
        etat = self._etat()
        self.assertFalse(etat["profil"])  # pas de Profile créé dans la base de test
        self.assertFalse(etat["seance"])
        self.assertFalse(etat["pesee"])

    def test_profil_coche_si_profil_existe(self):
        Profile.objects.create(
            user=self.user, sexe="H", date_naissance=datetime.date(2000, 1, 1),
            taille_cm=180, poids_kg=Decimal("80"), objectif=Objectif.MAINTIEN,
        )
        self.assertTrue(self._etat()["profil"])

    def test_seance_cochee_apres_un_workout_log(self):
        WorkoutLog.objects.create(
            user=self.user, workout_day=self.j1, date=datetime.date(2026, 6, 14)
        )
        self.assertTrue(self._etat()["seance"])

    def test_pesee_cochee_apres_une_mesure(self):
        BodyMeasurement.objects.create(
            user=self.user, date=datetime.date(2026, 6, 14), poids_kg=Decimal("80")
        )
        self.assertTrue(self._etat()["pesee"])

    def test_tout_termine_seulement_quand_les_trois_sont_faits(self):
        Profile.objects.create(
            user=self.user, sexe="H", date_naissance=datetime.date(2000, 1, 1),
            taille_cm=180, poids_kg=Decimal("80"), objectif=Objectif.MAINTIEN,
        )
        WorkoutLog.objects.create(
            user=self.user, workout_day=self.j1, date=datetime.date(2026, 6, 14)
        )
        self.assertFalse(services.etapes_demarrage(self.user)["tout_termine"])  # pas de pesée
        BodyMeasurement.objects.create(
            user=self.user, date=datetime.date(2026, 6, 14), poids_kg=Decimal("80")
        )
        self.assertTrue(services.etapes_demarrage(self.user)["tout_termine"])


class DashboardChecklistTests(TestCase):
    """La carte « Premiers pas » apparaît tant que les étapes ne sont pas finies."""

    def setUp(self):
        self.user = User.objects.create_user(username="ahmed", password="motdepasse123")
        Profile.objects.create(
            user=self.user, sexe="H", date_naissance=datetime.date(2000, 1, 1),
            taille_cm=180, poids_kg=Decimal("80"), objectif=Objectif.MAINTIEN,
        )
        self.client.force_login(self.user)

    def test_checklist_visible_quand_incomplete(self):
        response = self.client.get(reverse("tracking:dashboard"))
        self.assertContains(response, "Premiers pas")

    def test_checklist_masquee_quand_tout_coche(self):
        day = WorkoutDay.objects.create(
            program=Program.objects.create(
                user=self.user, nom="P", objectif=Objectif.MAINTIEN,
                date_debut=datetime.date(2026, 6, 1), split=Split.FULL_BODY, actif=True,
            ),
            jour_numero=1, nom="J1",
        )
        WorkoutLog.objects.create(user=self.user, workout_day=day, date=datetime.date(2026, 6, 14))
        BodyMeasurement.objects.create(
            user=self.user, date=datetime.date(2026, 6, 14), poids_kg=Decimal("80")
        )
        response = self.client.get(reverse("tracking:dashboard"))
        self.assertNotContains(response, "Premiers pas")


def _faux_profil(poids):
    """Profil minimal pour les fonctions pures (seul poids_kg est lu)."""
    return type("P", (), {"poids_kg": Decimal(str(poids))})()


class ObjectifHydratationTests(TestCase):
    def test_base_35ml_par_kg(self):
        # 35 ml/kg × 80 kg = 2800 ml, sans bonus.
        self.assertEqual(services.objectif_hydratation(_faux_profil(80)), 2800)

    def test_bonus_jour_entrainement(self):
        # 2800 + 500 ml de bonus un jour d'entraînement.
        self.assertEqual(
            services.objectif_hydratation(_faux_profil(80), jour_entrainement=True),
            3300,
        )

    def test_arrondi(self):
        # 35 × 72.5 = 2537.5 → arrondi à 2538.
        self.assertEqual(services.objectif_hydratation(_faux_profil("72.5")), 2538)


class EstJourEntrainementTests(TrackingTestBase):
    def test_vrai_si_seance_loggee_ce_jour(self):
        jour = datetime.date(2026, 6, 14)
        WorkoutLog.objects.create(user=self.user, workout_day=self.j1, date=jour)
        self.assertTrue(services.est_jour_entrainement(self.user, jour))

    def test_faux_sans_seance(self):
        self.assertFalse(
            services.est_jour_entrainement(self.user, datetime.date(2026, 6, 14))
        )

    def test_faux_si_seance_un_autre_jour(self):
        WorkoutLog.objects.create(
            user=self.user, workout_day=self.j1, date=datetime.date(2026, 6, 13)
        )
        self.assertFalse(
            services.est_jour_entrainement(self.user, datetime.date(2026, 6, 14))
        )


class AjouterEauTests(TrackingTestBase):
    def test_cumule_sur_la_journee(self):
        jour = datetime.date(2026, 6, 14)
        services.ajouter_eau(self.user, 250, date=jour)
        services.ajouter_eau(self.user, 500, date=jour)
        self.assertEqual(services.hydratation_du_jour(self.user, jour), 750)
        # Une seule ligne pour le jour (cumul, pas d'entrées multiples).
        self.assertEqual(WaterIntake.objects.filter(user=self.user).count(), 1)

    def test_reinitialisation_quotidienne(self):
        # De l'eau bue hier ne compte pas dans le total d'aujourd'hui.
        services.ajouter_eau(self.user, 1000, date=datetime.date(2026, 6, 13))
        self.assertEqual(
            services.hydratation_du_jour(self.user, datetime.date(2026, 6, 14)), 0
        )

    def test_isolation_par_utilisateur(self):
        autre = User.objects.create_user(username="autre", password="x")
        jour = datetime.date(2026, 6, 14)
        services.ajouter_eau(self.user, 500, date=jour)
        self.assertEqual(services.hydratation_du_jour(autre, jour), 0)

    def test_jour_vide_renvoie_zero(self):
        self.assertEqual(
            services.hydratation_du_jour(self.user, datetime.date(2026, 6, 14)), 0
        )


class ResumeHydratationTests(TrackingTestBase):
    def test_pourcentage_et_objectif(self):
        jour = datetime.date(2026, 6, 14)
        services.ajouter_eau(self.user, 1400, date=jour)
        resume = services.resume_hydratation(self.user, _faux_profil(80), date=jour)
        self.assertEqual(resume["objectif_ml"], 2800)  # pas de séance ce jour
        self.assertEqual(resume["bu_ml"], 1400)
        self.assertEqual(resume["pourcentage"], 50)
        self.assertFalse(resume["jour_entrainement"])

    def test_pourcentage_borne_a_100(self):
        jour = datetime.date(2026, 6, 14)
        WaterIntake.objects.create(user=self.user, date=jour, quantite_ml=5000)
        resume = services.resume_hydratation(self.user, _faux_profil(80), date=jour)
        self.assertEqual(resume["pourcentage"], 100)

    def test_objectif_inclut_bonus_les_jours_de_seance(self):
        jour = datetime.date(2026, 6, 14)
        WorkoutLog.objects.create(user=self.user, workout_day=self.j1, date=jour)
        resume = services.resume_hydratation(self.user, _faux_profil(80), date=jour)
        self.assertTrue(resume["jour_entrainement"])
        self.assertEqual(resume["objectif_ml"], 3300)


class AjouterEauEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ahmed", password="motdepasse123")
        Profile.objects.create(
            user=self.user, sexe="H", date_naissance=datetime.date(2000, 1, 1),
            taille_cm=180, poids_kg=Decimal("80"), objectif=Objectif.MAINTIEN,
        )
        self.client.force_login(self.user)
        self.url = reverse("tracking:ajouter_eau")

    def _post(self, quantite, ajax=True):
        kwargs = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"} if ajax else {}
        return self.client.post(self.url, {"quantite_ml": quantite}, **kwargs)

    def test_ajout_met_a_jour_et_renvoie_json(self):
        r1 = self._post(250)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["bu_ml"], 250)
        # Second ajout : cumul.
        r2 = self._post(500)
        self.assertEqual(r2.json()["bu_ml"], 750)
        self.assertEqual(r2.json()["objectif_ml"], 2800)

    def test_quantite_hors_plage_rejetee(self):
        self.assertEqual(self._post(0).status_code, 400)
        self.assertEqual(self._post(2001).status_code, 400)

    def test_quantite_non_numerique_rejetee(self):
        self.assertEqual(self._post("abc").status_code, 400)

    def test_login_requis(self):
        self.client.logout()
        r = self._post(250)
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("/dashboard", r.url)  # redirigé vers le login

    def test_scope_utilisateur(self):
        autre = User.objects.create_user(username="autre", password="x")
        self._post(250)
        self.assertEqual(WaterIntake.objects.filter(user=self.user).count(), 1)
        self.assertEqual(WaterIntake.objects.filter(user=autre).count(), 0)

    def test_fallback_sans_ajax_redirige_vers_dashboard(self):
        r = self._post(250, ajax=False)
        self.assertRedirects(r, reverse("tracking:dashboard"))
        self.assertEqual(services.hydratation_du_jour(self.user), 250)
