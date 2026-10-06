# Generated migration for avatar_choice field
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_add_profile_thumbnails'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='avatar_choice',
            field=models.CharField(max_length=64, null=True, blank=True),
        ),
    ]
