from django.contrib import admin

from .models import Exercise, Program, WorkoutDay, WorkoutExercise


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = (
        "nom", "groupe_musculaire", "type", "niveau_minimum",
        "source", "a_valider", "guide_a_valider",
    )
    # `a_valider` / `guide_a_valider` en tête : filtres clés pour retrouver
    # respectivement les exercices créés par l'IA et les guides générés par l'IA.
    list_filter = (
        "a_valider", "guide_a_valider", "groupe_musculaire", "type",
        "materiel_requis", "niveau_minimum",
    )
    search_fields = ("nom", "nom_en")
    list_editable = ("a_valider", "guide_a_valider")
    actions = ["valider_exercices", "valider_guides"]

    @admin.display(description="source", boolean=True)
    def source(self, obj: Exercise) -> bool:
        """Indique l'origine : True = IA (en attente de validation), False = catalogue."""
        return obj.a_valider

    @admin.action(description="Valider les exercices sélectionnés")
    def valider_exercices(self, request, queryset):
        """Validation en lot des exercices créés par l'IA (`a_valider` → False)."""
        nb = queryset.update(a_valider=False)
        self.message_user(request, f"{nb} exercice(s) validé(s).")

    @admin.action(description="Valider les guides générés par l'IA")
    def valider_guides(self, request, queryset):
        """Validation en lot des guides débutant générés par l'IA (`guide_a_valider` → False)."""
        nb = queryset.update(guide_a_valider=False)
        self.message_user(request, f"{nb} guide(s) validé(s).")


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
