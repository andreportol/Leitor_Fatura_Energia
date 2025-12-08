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
    valor_credito = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    password = models.CharField(max_length=128, default='123456')
    prompt_template = models.TextField(
        verbose_name='Diretrizes para IA', 
        blank=True, 
        null=True,                          
        default= ''' Regras de Negócio:
        - "nome do cliente"
        - "data de emissao"
        - "data de vencimento"
        - "codigo do cliente - uc"
        - "mes de referencia"
        - "consumo kwh"
        - "valor a pagar"
        - "Economia" 
        - "historico de consumo" (lista de objetos com "mês" e "consumo" em ordem cronológica se possível)
        - "saldo acumulado"
        - "preco unit com tributos"
        - "Energia Atv Injetada"
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
