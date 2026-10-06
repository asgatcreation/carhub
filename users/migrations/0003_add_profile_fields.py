"""Add missing Profile fields created after initial migrations.

This migration adds the fields that are present in `users.models.Profile`
but missing from the current database schema (e.g., `middle_name`,
`gender`, `race`, `state_of_origin`, `lga_of_origin`, `city`, `receive_news`).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_alter_customuser_managers"),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='middle_name',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='profile',
            name='gender',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='profile',
            name='race',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='profile',
            name='state_of_origin',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='profile',
            name='lga_of_origin',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='profile',
            name='city',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='profile',
            name='receive_news',
            field=models.BooleanField(default=False),
        ),
    ]
