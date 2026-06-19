from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("days/<int:day>/", views.day_detail, name="day-detail"),
    path("script/", views.generate_script, name="generate-script"),
    path("audio/", views.generate_audio, name="generate-audio"),
]
