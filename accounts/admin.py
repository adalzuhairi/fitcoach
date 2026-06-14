from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Profile, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    pass


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "sexe", "objectif", "niveau", "materiel", "poids_kg")
    list_filter = ("sexe", "objectif", "niveau", "activite", "materiel")
    search_fields = ("user__username", "user__email")
