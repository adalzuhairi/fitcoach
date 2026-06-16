"""Logique métier de l'app tracking (logs de séances, mesures, graphiques).

Fonctions au service du dashboard :
- `prochaine_seance` : prochaine journée à réaliser (rotation du split).
- `poids_actuel` : dernière pesée connue (sinon poids du profil).
- `historique_poids` : série temporelle pour le mini-graphique de progression.

Mesures corporelles :
- `enregistrer_mesure` : crée/met à jour une pesée (clé user + date).
- `historique_mesures` : série complète (poids + tours) pour Chart.js.

Progression (à partir des séries loggées) :
- `exercices_logges` : exercices avec au moins une série enregistrée.
- `progression_charge` : charge max par séance pour un exercice.
- `volume_hebdomadaire` : volume total (reps × charge) par semaine.
"""

from __future__ import annotations

import datetime

# Mensurations optionnelles tracées sur les graphiques (hors poids).
CHAMPS_TOURS = ("tour_taille", "tour_bras", "tour_poitrine", "tour_cuisses")

# Hydratation — base de référence et bonus les jours d'entraînement.
EAU_ML_PAR_KG = 35
EAU_BONUS_ENTRAINEMENT_ML = 500


def etapes_demarrage(user):
    """Checklist de démarrage du dashboard, reflétant l'état réel du compte.

    Chaque étape s'appuie sur un signal concret en base (profil créé, première
    séance loggée, première pesée enregistrée) : aucune heuristique, la
    checklist est donc honnête. `tout_termine` permet de masquer la carte une
    fois les premiers pas accomplis. L'item profil est coché d'emblée sur le
    dashboard (le middleware garantit qu'un profil existe) : c'est volontaire,
    il sert de point de départ acquis.
    """
    from accounts.models import Profile
    from tracking.models import BodyMeasurement, WorkoutLog

    etapes = [
        {
            "cle": "profil",
            "label": "Profil complété",
            "done": Profile.objects.filter(user=user).exists(),
            "url_name": "accounts:profil",
        },
        {
            "cle": "seance",
            "label": "Lance ta première séance",
            "done": WorkoutLog.objects.filter(user=user).exists(),
            "url_name": "training:programme",
        },
        {
            "cle": "pesee",
            "label": "Enregistre ta première pesée",
            "done": BodyMeasurement.objects.filter(user=user).exists(),
            "url_name": "tracking:mesures",
        },
    ]
    return {"etapes": etapes, "tout_termine": all(e["done"] for e in etapes)}


def objectif_hydratation(profile, jour_entrainement=False):
    """Objectif d'eau du jour en ml : 35 ml/kg de poids de corps, + bonus.

    Le bonus (`EAU_BONUS_ENTRAINEMENT_ML`) s'ajoute les jours où l'utilisateur
    s'entraîne (transpiration). Renvoie un entier (ml).
    """
    base = round(EAU_ML_PAR_KG * float(profile.poids_kg))
    if jour_entrainement:
        base += EAU_BONUS_ENTRAINEMENT_ML
    return base


def est_jour_entrainement(user, date=None):
    """True si l'utilisateur a loggé une séance ce jour (signal concret)."""
    from tracking.models import WorkoutLog

    date = date or datetime.date.today()
    return WorkoutLog.objects.filter(user=user, date=date).exists()


def ajouter_eau(user, quantite_ml, date=None):
    """Ajoute `quantite_ml` à la consommation du jour (incrément atomique).

    Crée la ligne (user, date) si absente, sinon cumule via F() pour éviter
    toute condition de course. Renvoie l'instance WaterIntake à jour.
    """
    from django.db.models import F

    from tracking.models import WaterIntake

    date = date or datetime.date.today()
    intake, cree = WaterIntake.objects.get_or_create(
        user=user, date=date, defaults={"quantite_ml": quantite_ml}
    )
    if not cree:
        intake.quantite_ml = F("quantite_ml") + quantite_ml
        intake.save(update_fields=["quantite_ml"])
        intake.refresh_from_db()
    return intake


def hydratation_du_jour(user, date=None):
    """Quantité d'eau bue aujourd'hui (ml), 0 si aucune entrée."""
    from tracking.models import WaterIntake

    date = date or datetime.date.today()
    intake = WaterIntake.objects.filter(user=user, date=date).first()
    return intake.quantite_ml if intake is not None else 0


def resume_hydratation(user, profile, date=None):
    """Résumé du jour pour le dashboard : bu / objectif / % / jour d'entraînement.

    Le pourcentage est borné à 100 pour l'affichage de la barre de progression.
    """
    date = date or datetime.date.today()
    jour_entrainement = est_jour_entrainement(user, date)
    objectif = objectif_hydratation(profile, jour_entrainement)
    bu = hydratation_du_jour(user, date)
    pourcentage = min(100, round(bu / objectif * 100)) if objectif else 0
    return {
        "bu_ml": bu,
        "objectif_ml": objectif,
        "pourcentage": pourcentage,
        "jour_entrainement": jour_entrainement,
    }


def prochaine_seance(user, program):
    """Prochaine journée d'entraînement à réaliser dans le programme actif.

    Rotation du split : on repart de la journée qui suit la dernière séance
    loggée (cycle), ou de la première journée s'il n'y a aucun historique.
    Renvoie None si le programme n'a aucune journée.
    """
    from tracking.models import WorkoutLog

    if program is None:
        return None

    jours = list(program.workout_days.all())
    if not jours:
        return None

    dernier_log = (
        WorkoutLog.objects.filter(user=user, workout_day__program=program)
        .exclude(workout_day__isnull=True)
        .order_by("-date", "-id")
        .first()
    )
    if dernier_log is None:
        return jours[0]

    # Index de la journée suivante (cyclique).
    ids = [j.id for j in jours]
    try:
        position = ids.index(dernier_log.workout_day_id)
    except ValueError:
        return jours[0]
    return jours[(position + 1) % len(jours)]


def poids_actuel(user, profile=None):
    """Poids le plus récent : dernière mesure corporelle, sinon poids du profil."""
    from tracking.models import BodyMeasurement

    mesure = BodyMeasurement.objects.filter(user=user).order_by("-date").first()
    if mesure is not None:
        return mesure.poids_kg
    return profile.poids_kg if profile is not None else None


def historique_poids(user, limit=12):
    """Série {date, poids} pour le graphique de progression (ordre chronologique).

    Prend les `limit` dernières mesures puis les remet dans l'ordre croissant
    afin que Chart.js trace de gauche (ancien) à droite (récent).
    """
    from tracking.models import BodyMeasurement

    mesures = list(
        BodyMeasurement.objects.filter(user=user).order_by("-date")[:limit]
    )
    mesures.reverse()
    return [
        {"date": m.date.isoformat(), "poids": float(m.poids_kg)} for m in mesures
    ]


def enregistrer_mesure(user, donnees):
    """Crée (ou met à jour si la date existe déjà) une mesure corporelle.

    `donnees` est un dict de champs validés (typiquement `form.cleaned_data`).
    Le poids est obligatoire ; les mensurations/photo absentes (None) ne sont
    pas écrasées sur une mise à jour. La clé d'unicité est (user, date).
    """
    from tracking.models import BodyMeasurement

    donnees = dict(donnees)
    date = donnees.pop("date", None) or datetime.date.today()
    defaults = {k: v for k, v in donnees.items() if v is not None}

    mesure, _ = BodyMeasurement.objects.update_or_create(
        user=user, date=date, defaults=defaults
    )
    return mesure


def historique_mesures(user, limit=None):
    """Série chronologique (poids + chaque tour) pour les graphiques Chart.js.

    Les valeurs absentes sont sérialisées en None (Chart.js coupe la ligne).
    `limit` borne aux N pesées les plus récentes ; None = tout l'historique.
    """
    from tracking.models import BodyMeasurement

    qs = BodyMeasurement.objects.filter(user=user).order_by("-date")
    if limit:
        qs = qs[:limit]
    mesures = list(qs)
    mesures.reverse()

    serie = []
    for m in mesures:
        point = {"date": m.date.isoformat(), "poids": float(m.poids_kg)}
        for champ in CHAMPS_TOURS:
            valeur = getattr(m, champ)
            point[champ] = float(valeur) if valeur is not None else None
        serie.append(point)
    return serie


def exercices_logges(user):
    """Exercices pour lesquels l'utilisateur a enregistré au moins une série."""
    from training.models import Exercise
    from tracking.models import SetLog

    ids = (
        SetLog.objects.filter(workout_log__user=user)
        .values_list("workout_exercise__exercise", flat=True)
        .distinct()
    )
    return list(Exercise.objects.filter(id__in=ids).order_by("nom"))


def progression_charge(user, exercise):
    """Charge maximale par séance (date) pour un exercice, ordre chronologique.

    Agrège toutes les séries de l'exercice (quelle que soit la journée/le
    programme) : un point = la charge la plus lourde soulevée ce jour-là.
    """
    from django.db.models import Max

    from tracking.models import SetLog

    lignes = (
        SetLog.objects.filter(
            workout_log__user=user, workout_exercise__exercise=exercise
        )
        .values("workout_log__date")
        .annotate(charge_max=Max("charge_kg"))
        .order_by("workout_log__date")
    )
    return [
        {"date": ligne["workout_log__date"].isoformat(), "charge": float(ligne["charge_max"])}
        for ligne in lignes
    ]


def volume_hebdomadaire(user, n_semaines=8, aujourdhui=None):
    """Volume total (Σ reps × charge) par semaine ISO, sur les `n_semaines` dernières.

    Agrégé en Python (portable SQLite/Postgres). Les semaines sans entraînement
    apparaissent à 0 pour une courbe/barres continue. Chaque semaine est repérée
    par le lundi qui la débute.
    """
    from tracking.models import SetLog

    aujourdhui = aujourdhui or datetime.date.today()
    lundi_courant = aujourdhui - datetime.timedelta(days=aujourdhui.weekday())
    premier_lundi = lundi_courant - datetime.timedelta(weeks=n_semaines - 1)

    rows = SetLog.objects.filter(
        workout_log__user=user, workout_log__date__gte=premier_lundi
    ).values_list("workout_log__date", "repetitions_faites", "charge_kg")

    par_semaine = {}
    for date, reps, charge in rows:
        lundi = date - datetime.timedelta(days=date.weekday())
        par_semaine[lundi] = par_semaine.get(lundi, 0) + reps * float(charge)

    serie = []
    for i in range(n_semaines):
        lundi = premier_lundi + datetime.timedelta(weeks=i)
        serie.append({"semaine": lundi.isoformat(), "volume": round(par_semaine.get(lundi, 0))})
    return serie
