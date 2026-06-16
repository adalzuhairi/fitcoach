"""Tests du moteur de recommandation de compléments (logique métier, sans IA)."""

import datetime
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Objectif, Profile, Sexe
from supplements import services
from supplements.models import Categorie, NiveauPreuve, Supplement

User = get_user_model()


def _profile_stub(objectif, preferences=""):
    """Profil minimal pour la reco (objectif + préférences alimentaires)."""
    return SimpleNamespace(objectif=objectif, preferences_alimentaires=preferences)


class RecommanderComplementsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.creatine = Supplement.objects.create(
            nom="Créatine", categorie=Categorie.CREATINE, niveau_preuve=NiveauPreuve.ELEVE
        )
        cls.whey = Supplement.objects.create(
            nom="Whey", categorie=Categorie.PROTEINE, niveau_preuve=NiveauPreuve.ELEVE,
            exclu_pour=["vegan"], priorite=1,
        )
        cls.vegetale = Supplement.objects.create(
            nom="Protéine végétale", categorie=Categorie.PROTEINE,
            niveau_preuve=NiveauPreuve.ELEVE, priorite=2,
        )
        cls.caseine = Supplement.objects.create(
            nom="Caséine", categorie=Categorie.PROTEINE, niveau_preuve=NiveauPreuve.MODERE,
            exclu_pour=["vegan"], priorite=3,
        )
        cls.cafeine = Supplement.objects.create(
            nom="Caféine", categorie=Categorie.PRE_WORKOUT, niveau_preuve=NiveauPreuve.ELEVE
        )
        cls.bcaa = Supplement.objects.create(
            nom="BCAA", categorie=Categorie.ACIDES_AMINES, niveau_preuve=NiveauPreuve.FAIBLE
        )
        cls.inactif = Supplement.objects.create(
            nom="Vieux produit", categorie=Categorie.CREATINE,
            niveau_preuve=NiveauPreuve.ELEVE, actif=False,
        )

    def test_filtre_par_objectif(self):
        # PRISE_DE_MASSE n'inclut pas la catégorie pré-workout : la caféine est exclue.
        resultats = services.recommander_complements(
            _profile_stub(Objectif.PRISE_DE_MASSE)
        )
        self.assertIn(self.creatine, resultats)
        self.assertIn(self.whey, resultats)
        self.assertNotIn(self.cafeine, resultats)
        # ACIDES_AMINES n'est dans aucun objectif : les BCAA ne sont jamais conseillés.
        self.assertNotIn(self.bcaa, resultats)

    def test_pre_workout_conseille_en_seche(self):
        resultats = services.recommander_complements(_profile_stub(Objectif.SECHE))
        self.assertIn(self.cafeine, resultats)

    def test_exclut_inactif(self):
        resultats = services.recommander_complements(
            _profile_stub(Objectif.FORCE)
        )
        self.assertNotIn(self.inactif, resultats)

    def test_filtre_regime_vegan(self):
        # Profil vegan : whey et caséine (issues du lait) doivent disparaître.
        resultats = services.recommander_complements(
            _profile_stub(Objectif.PRISE_DE_MASSE, preferences="je mange vegan")
        )
        self.assertNotIn(self.whey, resultats)
        self.assertNotIn(self.caseine, resultats)
        self.assertIn(self.vegetale, resultats)

    def test_tri_priorite_objectif_puis_preuve(self):
        # FORCE : créatine (catégorie prioritaire) avant les protéines.
        resultats = services.recommander_complements(_profile_stub(Objectif.FORCE))
        self.assertEqual(resultats[0], self.creatine)
        # À catégorie égale, le champ priorite décide : whey (1) avant végétale (2).
        proteines = [s for s in resultats if s.categorie == Categorie.PROTEINE]
        self.assertEqual(proteines, [self.whey, self.vegetale, self.caseine])

    def test_profile_none_renvoie_vide(self):
        self.assertEqual(services.recommander_complements(None), [])


class ComplementsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Supplement.objects.create(
            nom="Créatine", categorie=Categorie.CREATINE, niveau_preuve=NiveauPreuve.ELEVE,
            benefices="Augmente la force.",
        )
        cls.user = User.objects.create_user(username="u", email="u@ex.com", password="x")
        Profile.objects.create(
            user=cls.user,
            sexe=Sexe.HOMME,
            date_naissance=datetime.date(1995, 1, 1),
            taille_cm=180,
            poids_kg=80,
            objectif=Objectif.PRISE_DE_MASSE,
            tutoriel_vu=True,
        )

    def test_page_complements_ok(self):
        self.client.force_login(self.user)
        r = self.client.get("/complements/")
        self.assertEqual(r.status_code, 200)
        contenu = r.content.decode()
        self.assertIn("Créatine", contenu)
        # Bandeau d'avertissement (responsabilité) présent.
        self.assertIn("ne sont pas obligatoires", contenu)
        self.assertIn("professionnel de santé", contenu)

    def test_redirige_si_non_connecte(self):
        r = self.client.get("/complements/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)
