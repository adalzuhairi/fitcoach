from django.urls import path

from . import views

app_name = "nutrition"

urlpatterns = [
    path("", views.ma_nutrition, name="ma_nutrition"),
]
