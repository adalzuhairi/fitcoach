from django.contrib import admin

from .models import (
    BodyMeasurement,
    SetLog,
    SubstitutionSeance,
    WaterIntake,
    WorkoutLog,
)


class SetLogInline(admin.TabularInline):
    model = SetLog
    extra = 0


@admin.register(WorkoutLog)
class WorkoutLogAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "workout_day", "duree_minutes", "ressenti")
    list_filter = ("date",)
    search_fields = ("user__username",)
    inlines = [SetLogInline]


@admin.register(BodyMeasurement)
class BodyMeasurementAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "poids_kg", "tour_taille", "tour_bras")
    list_filter = ("date",)
    search_fields = ("user__username",)


@admin.register(SubstitutionSeance)
class SubstitutionSeanceAdmin(admin.ModelAdmin):
    list_display = ("workout_log", "workout_exercise", "exercise_substitut", "cree_le")
    search_fields = ("workout_log__user__username",)


@admin.register(WaterIntake)
class WaterIntakeAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "quantite_ml")
    list_filter = ("date",)
    search_fields = ("user__username",)
