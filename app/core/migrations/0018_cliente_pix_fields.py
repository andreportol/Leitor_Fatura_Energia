from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_alter_cliente_template_fatura'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='pix_key',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Chave PIX'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='pix_qrcode',
            field=models.ImageField(blank=True, null=True, upload_to='pix_qrcodes/', verbose_name='QR Code PIX'),
        ),
    ]
