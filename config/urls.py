from django.conf import settings
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

if settings.PUBLIC_DEMO:
    # Public deployment exposes only the isolated sandbox. No shared password
    # login or unbounded classic commands are reachable through this URLconf.
    from desk import demo_urls

    urlpatterns = demo_urls.urlpatterns
