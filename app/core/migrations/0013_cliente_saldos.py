from decimal import Decimal

from django.db import migrations, models


def forwards(apps, schema_editor):
    Cliente = apps.get_model('core', 'Cliente')
    for cliente in Cliente.objects.all():
        saldo = cliente.valor_credito or Decimal('0')
        cliente.saldo_atual = saldo
        cliente.saldo_final = saldo
        # valor_credito passa a ser usado como delta; zera para evitar duplicidade ao salvar.
        cliente.valor_credito = Decimal('0')
        cliente.save(update_fields=['saldo_atual', 'saldo_final', 'valor_credito'])


def backwards(apps, schema_editor):
    Cliente = apps.get_model('core', 'Cliente')
    for cliente in Cliente.objects.all():
        # retorna saldo_atual para valor_credito
        cliente.valor_credito = cliente.saldo_atual or Decimal('0')
        cliente.save(update_fields=['valor_credito'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_alter_credithistory_amount_alter_credithistory_balance_after'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='saldo_atual',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10, verbose_name='Saldo atual'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='saldo_final',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10, verbose_name='Saldo final'),
        ),
        migrations.RunPython(forwards, backwards),
    ]
