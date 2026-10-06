"""Add `profile_image` field to Profile model.

Generated to synchronize the database with the current `Profile` model which
includes `profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)`.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_expand_application_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='profile_image',
            field=models.ImageField(blank=True, null=True, upload_to='profile_images/'),
        ),
    ]
