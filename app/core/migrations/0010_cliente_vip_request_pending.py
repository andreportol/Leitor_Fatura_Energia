from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_credithistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='vip_request_pending',
            field=models.BooleanField(default=False),
        ),
    ]
