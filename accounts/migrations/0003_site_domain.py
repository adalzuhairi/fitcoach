"""Configure le Site par défaut (framework django.contrib.sites).

allauth s'appuie sur l'objet Site (pk = SITE_ID) pour construire les URL
absolues (ex: liens de réinitialisation de mot de passe). Le domaine dépend de
l'environnement, on le lit donc dans une variable d'env :

    DJANGO_SITE_DOMAIN  (défaut "localhost:8000" en dev)
    DJANGO_SITE_NAME    (défaut "FitCoach")

En prod : DJANGO_SITE_DOMAIN=fitcoach.infotechno.eu:4443
"""

import os

from django.conf import settings
from django.db import migrations


def definir_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    domaine = os.environ.get("DJANGO_SITE_DOMAIN", "localhost:8000")
    nom = os.environ.get("DJANGO_SITE_NAME", "FitCoach")
    Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": domaine, "name": nom},
    )


def reinitialiser_site(apps, schema_editor):
    # Remet la valeur par défaut de Django pour permettre un rollback propre.
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": "example.com", "name": "example.com"},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_profile"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(definir_site, reinitialiser_site),
    ]
