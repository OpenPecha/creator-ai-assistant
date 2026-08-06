from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("days/<int:day>/", views.day_detail, name="day-detail"),
    path("days/<int:day>/share-image/", views.day_share_image, name="day-share-image"),
    path("verse-summary/", views.verse_summary_view, name="verse-summary"),
    path("script/", views.generate_script, name="generate-script"),
    path("structure/", views.generate_structure, name="generate-structure"),
    path("audio/", views.generate_audio, name="generate-audio"),
    path("save-for-review/", views.save_for_review, name="save-for-review"),
]
