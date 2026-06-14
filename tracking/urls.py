from django.urls import path

from . import views

app_name = "tracking"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("progression/", views.progression, name="progression"),
    path("mesures/", views.mesures, name="mesures"),
    path("mesures/<int:pk>/modifier/", views.modifier_mesure, name="modifier_mesure"),
    path("mesures/<int:pk>/supprimer/", views.supprimer_mesure, name="supprimer_mesure"),
]
