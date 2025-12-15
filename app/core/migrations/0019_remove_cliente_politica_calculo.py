from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_cliente_pix_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cliente',
            name='politica_calculo',
        ),
    ]
