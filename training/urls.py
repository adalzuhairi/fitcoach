from django.urls import path

from . import views

app_name = "training"

urlpatterns = [
    path("programme/", views.programme, name="programme"),
    path("seance/<int:workout_day_id>/", views.seance, name="seance"),
    path("seance/serie/", views.enregistrer_serie, name="enregistrer_serie"),
    path("seance/<int:log_id>/terminer/", views.terminer_seance, name="terminer_seance"),
]
