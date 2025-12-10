from django.conf import settings
from django.db import models

# Create your models here.
class Base(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Cliente(Base):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cliente',
        blank=True,
        null=True,
    )
    nome = models.CharField(verbose_name='Nome', max_length=100, unique=True)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=15, blank=True, null=True)
    estado = models.CharField(max_length=50, blank=True, null=True)
    cidade = models.CharField(max_length=50, blank=True, null=True)
    is_ativo = models.BooleanField(default=True)
    is_VIP = models.BooleanField(default=False)
    vip_request_pending = models.BooleanField(default=False)
    saldo_atual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Saldo atual')
    valor_credito = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Valor do crédito')
    saldo_final = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Saldo final')
    password = models.CharField(max_length=128, default='123456')
    prompt_template = models.TextField(
        verbose_name='Diretrizes para IA', 
        blank=True, 
        null=True,                          
        default= ''' 
        "valor a pagar" =  energia_atv_injetada_valor * 0.7
        "Economia"  =  energia_atv_injetada_valor * 0.3
        ''')

    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nome']


class ClienteContato(Base):
    """
    Contato de envio de fatura para clientes VIP.
    """
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='contatos',
    )
    nome = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f'{self.nome} ({self.email or "sem e-mail"})'

    class Meta:
        verbose_name = 'Contato'
        verbose_name_plural = 'Contatos'
        ordering = ['nome']
        unique_together = (('cliente', 'email'),)


class CreditHistory(Base):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='credit_history',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor inserido')
    balance_after = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Saldo após')
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Histórico de Crédito'
        verbose_name_plural = 'Históricos de Créditos'
        ordering = ['-created_at']

    def __str__(self):
        sinal = '+' if self.amount and self.amount > 0 else ''
        return f'Movimentação {sinal}{self.amount}'
