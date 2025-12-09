from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_cliente_vip_request_pending'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='credithistory',
            name='kind',
        ),
    ]
