from django.urls import path
from django.views.generic import RedirectView

from . import demo_views, views

urlpatterns = [
    path("", RedirectView.as_view(url="/demo/en/", permanent=False)),
    path("demo/<str:locale>/", demo_views.home, name="demo-home"),
    path("demo/<str:locale>/start/", demo_views.start, name="demo-start"),
    path("demo/<str:locale>/role/", demo_views.role, name="demo-role"),
    path("demo/<str:locale>/command/", demo_views.command, name="demo-command"),
    path("demo/<str:locale>/evidence.json", demo_views.evidence, name="demo-evidence"),
    path("health/", views.health),
]
