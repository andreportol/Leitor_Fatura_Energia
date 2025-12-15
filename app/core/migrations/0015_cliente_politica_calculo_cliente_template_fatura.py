from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_alter_cliente_valor_credito"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="politica_calculo",
            field=models.CharField(
                choices=[("padrao", "Padrão"), ("vip", "VIP")],
                default="padrao",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="template_fatura",
            field=models.CharField(
                default="energisa_padrao.html",
                max_length=100,
            ),
        ),
    ]
