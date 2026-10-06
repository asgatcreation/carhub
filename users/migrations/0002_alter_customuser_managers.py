"""Minimal migration to restore expected 0002 migration file.

This migration mirrors an alter-manager migration that existed in the
original repository history. It is safe and required so that later
migrations (recorded in the DB) have their file counterparts present.
"""
from django.db import migrations
import users.models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='customuser',
            managers=[('objects', users.models.CustomUserManager())],
        ),
    ]
