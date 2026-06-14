from django.urls import path

from . import views

app_name = "nutrition"

urlpatterns = [
    path("", views.ma_nutrition, name="ma_nutrition"),
    path("repas/<int:meal_id>/recettes/", views.recettes_repas, name="recettes_repas"),
    path("repas/<int:meal_id>/recettes/generer/", views.generer_recettes, name="generer_recettes"),
]
