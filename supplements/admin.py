from django.contrib import admin

from .models import Supplement


@admin.register(Supplement)
class SupplementAdmin(admin.ModelAdmin):
    list_display = ("nom", "categorie", "niveau_preuve", "actif")
    list_filter = ("categorie", "niveau_preuve", "actif")
    search_fields = ("nom", "nom_en")
    list_editable = ("actif",)
