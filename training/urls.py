from django.urls import path

from . import views

app_name = "training"

urlpatterns = [
    path("exercices/", views.bibliotheque, name="bibliotheque"),
    path("exercices/<int:exercice_id>/", views.exercice, name="exercice"),
    path("programme/", views.programme, name="programme"),
    path("seance/<int:workout_day_id>/", views.seance, name="seance"),
    path("seance/serie/", views.enregistrer_serie, name="enregistrer_serie"),
    path(
        "seance/<int:we_id>/alternatives/",
        views.alternatives_exercice,
        name="alternatives",
    ),
    path("seance/substituer/", views.substituer, name="substituer"),
    path(
        "seance/annuler-substitution/",
        views.annuler_substitution,
        name="annuler_substitution",
    ),
    path("seance/<int:log_id>/terminer/", views.terminer_seance, name="terminer_seance"),
]
