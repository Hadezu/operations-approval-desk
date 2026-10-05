from django.contrib.auth import views as auth
from django.urls import path

from desk import views

urlpatterns = [
    path("login/", auth.LoginView.as_view(template_name="desk/login.html")),
    path("logout/", auth.LogoutView.as_view()),
    path("", views.queue, name="queue"),
    path("requests/<uuid:pk>/", views.detail, name="detail"),
    path("teams/<int:team_id>/commands/", views.command, name="command"),
    path("requests/<uuid:pk>/evidence.json", views.evidence, name="evidence"),
    path("health/", views.health),
]
