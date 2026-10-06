from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone

from desk.demo import cleanup


class Command(BaseCommand):
    help = "Delete expired synthetic demo tenants and expired Django sessions."

    def handle(self, **options):
        count = cleanup()
        Session.objects.filter(expire_date__lt=timezone.now()).delete()
        self.stdout.write(f"Removed {count} expired demo workspaces.")
