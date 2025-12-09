from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_remove_credithistory_kind'),
    ]

    operations = [
        migrations.AlterField(
            model_name='credithistory',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Valor inserido'),
        ),
        migrations.AlterField(
            model_name='credithistory',
            name='balance_after',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Saldo após'),
        ),
    ]
