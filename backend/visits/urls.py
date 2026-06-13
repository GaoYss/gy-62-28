from django.urls import path

from . import views


urlpatterns = [
    path("", views.visits_collection),
    path("summary/", views.visits_summary),
    path("export/", views.visits_export),
    path("<int:pk>/", views.visit_detail),
]
