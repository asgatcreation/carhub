from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0016_notification'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='chat_enabled',
            field=models.BooleanField(default=True),
        ),
    ]
