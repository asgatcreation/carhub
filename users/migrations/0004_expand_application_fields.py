"""Add expanded detail fields to Application model for richer application forms.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_add_profile_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='full_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='application',
            name='phone',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='application',
            name='address',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='application',
            name='id_type',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='application',
            name='id_number',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='application',
            name='company_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='application',
            name='vehicle_details',
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name='application',
            name='experience_years',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
