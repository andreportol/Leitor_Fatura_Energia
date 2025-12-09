from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_cliente_is_vip'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreditHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('kind', models.CharField(choices=[('credit', 'Crédito adicionado'), ('debit', 'Crédito utilizado')], max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('balance_after', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('description', models.CharField(blank=True, max_length=255, null=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='credit_history', to='core.cliente')),
            ],
            options={
                'verbose_name': 'Histórico de Crédito',
                'verbose_name_plural': 'Históricos de Créditos',
                'ordering': ['-created_at'],
                'abstract': False,
            },
        ),
    ]
