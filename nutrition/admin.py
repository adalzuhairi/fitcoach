from django.contrib import admin

from .models import Meal, NutritionPlan, Recipe


class MealInline(admin.TabularInline):
    model = Meal
    extra = 0


@admin.register(NutritionPlan)
class NutritionPlanAdmin(admin.ModelAdmin):
    list_display = ("user", "calories_cibles", "proteines_g", "glucides_g", "lipides_g", "actif")
    list_filter = ("actif",)
    search_fields = ("user__username",)
    inlines = [MealInline]


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("nom", "calories", "proteines_g", "temps_preparation_min", "generee_par_ia")
    list_filter = ("generee_par_ia",)
    search_fields = ("nom",)
