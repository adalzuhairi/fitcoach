from django.contrib import admin

from .models import Exercise, Program, WorkoutDay, WorkoutExercise


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("nom", "groupe_musculaire", "type", "niveau_minimum", "a_valider")
    list_filter = ("groupe_musculaire", "type", "materiel_requis", "niveau_minimum", "a_valider")
    search_fields = ("nom", "nom_en")
    list_editable = ("a_valider",)


class WorkoutExerciseInline(admin.TabularInline):
    model = WorkoutExercise
    extra = 0


class WorkoutDayInline(admin.TabularInline):
    model = WorkoutDay
    extra = 0


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("nom", "user", "objectif", "split", "actif", "genere_par_ia", "cree_le")
    list_filter = ("objectif", "split", "actif", "genere_par_ia")
    search_fields = ("nom", "user__username")
    inlines = [WorkoutDayInline]


@admin.register(WorkoutDay)
class WorkoutDayAdmin(admin.ModelAdmin):
    list_display = ("nom", "program", "jour_numero")
    inlines = [WorkoutExerciseInline]
