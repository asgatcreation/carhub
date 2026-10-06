"""Add thumbnail fields for profile images."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_add_profile_image"),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='profile_image_small',
            field=models.ImageField(blank=True, null=True, upload_to='profile_images/thumbnails/'),
        ),
        migrations.AddField(
            model_name='profile',
            name='profile_image_medium',
            field=models.ImageField(blank=True, null=True, upload_to='profile_images/thumbnails/'),
        ),
    ]
