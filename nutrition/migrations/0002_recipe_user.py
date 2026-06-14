"""Rend les recettes privées : ajout de Recipe.user (FK obligatoire).

La table Recipe est vide à ce stade (recettes générées à la demande, aucune
donnée de prod), on ajoute donc directement une FK non-nullable sans valeur
par défaut artificielle.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("nutrition", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipe",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="recipes",
                to=settings.AUTH_USER_MODEL,
                verbose_name="utilisateur",
            ),
        ),
    ]
