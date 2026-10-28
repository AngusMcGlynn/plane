"""Create the instance admin on first boot so /god-mode is never left unclaimed.

Reads PLANE_ADMIN_EMAIL and PLANE_ADMIN_PASSWORD. Does nothing once an admin exists.
"""
import os
import time
import uuid

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction

from plane.db.models import Profile, User
from plane.license.models import Instance, InstanceAdmin


class Command(BaseCommand):
    help = "Create the Plane instance admin from environment variables if none exists"

    def handle(self, *args, **options):
        instance = None
        for _ in range(150):
            instance = Instance.objects.first()
            if instance:
                break
            time.sleep(2)
        if instance is None:
            self.stderr.write("Instance is not registered yet; skipping admin bootstrap")
            return
        if InstanceAdmin.objects.exists():
            self.stdout.write("Instance admin exists; nothing to do")
            return

        email = os.environ.get("PLANE_ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("PLANE_ADMIN_PASSWORD", "")
        if not email or not password:
            self.stderr.write("PLANE_ADMIN_EMAIL or PLANE_ADMIN_PASSWORD missing; claim the instance at /god-mode/")
            return

        with transaction.atomic():
            instance = Instance.objects.select_for_update().get(pk=instance.pk)
            if InstanceAdmin.objects.exists():
                return
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create(
                    email=email,
                    username=uuid.uuid4().hex,
                    password=make_password(password),
                    is_password_autoset=False,
                    is_active=True,
                )
                Profile.objects.create(user=user)
            InstanceAdmin.objects.create(user=user, instance=instance)
            instance.is_setup_done = True
            instance.instance_name = os.environ.get("PLANE_ORGANIZATION", "").strip() or instance.instance_name
            instance.save()
        cache.clear()
        self.stdout.write(f"Created instance admin {email}")
