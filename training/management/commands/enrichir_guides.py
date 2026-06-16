"""Enrichit le guide débutant des exercices via l'IA (sécurité/erreurs/muscles).

Usage :
    python manage.py enrichir_guides            # exercices au guide vide
    python manage.py enrichir_guides --force     # régénère TOUT (même rempli)
    python manage.py enrichir_guides --limit 5   # plafonne le nombre traité

Sûre et idempotente :
- saute les exercices dont le guide est déjà rempli (ne re-paie pas l'API),
  sauf avec --force ;
- ne plante pas si ANTHROPIC_API_KEY est absente (sortie propre) ;
- un échec sur un exercice n'interrompt pas le lot.

Après génération, relire/corriger dans l'admin (filtre « guide à valider »),
puis figer le résultat dans la fixture exercises.json (versionné, sans
dépendance API au déploiement).
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from coach import services
from training.models import Exercise


class Command(BaseCommand):
    help = "Génère le guide débutant des exercices (sécurité, erreurs, muscles) via l'IA."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Régénère le guide même pour les exercices déjà remplis.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Nombre maximum d'exercices à traiter (utile pour un test).",
        )

    def handle(self, *args, **options):
        if not settings.ANTHROPIC_API_KEY:
            self.stdout.write(
                self.style.WARNING(
                    "ANTHROPIC_API_KEY absente — aucun appel IA, rien à faire. "
                    "Renseigne la clé puis relance."
                )
            )
            return

        force = options["force"]
        limit = options["limit"]

        qs = Exercise.objects.order_by("groupe_musculaire", "nom")
        a_traiter = [ex for ex in qs if force or not ex.a_un_guide]
        ignores = qs.count() - len(a_traiter)
        if limit is not None:
            a_traiter = a_traiter[:limit]

        if not a_traiter:
            self.stdout.write(
                self.style.SUCCESS("Tous les guides sont déjà remplis (rien à générer).")
            )
            return

        self.stdout.write(
            f"{len(a_traiter)} exercice(s) à enrichir "
            f"({ignores} déjà rempli(s), ignoré(s))…"
        )

        succes = echecs = 0
        for ex in a_traiter:
            if services.generate_exercise_guide(ex):
                succes += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ {ex.nom}"))
            else:
                echecs += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {ex.nom} (échec, voir logs)"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé : {succes} guide(s) généré(s), {echecs} échec(s). "
                "À relire dans l'admin (filtre « guide à valider »)."
            )
        )
