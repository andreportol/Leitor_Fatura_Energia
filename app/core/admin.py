from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher, make_password
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from .models import Cliente, ClienteContato, CreditHistory

User = get_user_model()

# Branding for admin panel (fallback if manifest/static not ready)
def _safe_static(path: str) -> str:
    try:
        return static(path)
    except Exception:
        base = getattr(settings, 'STATIC_URL', '/static/')
        if not base.endswith('/'):
            base += '/'
        return f"{base}{path}"


logo_url = _safe_static('img/logomarca.png')
admin.site.site_header = mark_safe(f'<img src="{logo_url}" alt="ALP SISTEMAS" style="height:40px; vertical-align:middle; margin-right:8px;"> ALP SISTEMAS')
admin.site.site_title = 'ALP SISTEMAS'
admin.site.index_title = 'Painel Administrativo'


class ClienteAdminForm(forms.ModelForm):
    password = forms.CharField(
        label='Senha',
        required=False,
        widget=forms.PasswordInput(render_value=True),
    )

    class Meta:
        model = Cliente
        exclude = ('user',)

    def clean_password(self):
        password = self.cleaned_data.get('password', '')
        if not password:
            return password
        # Avoid double-hashing if the value already looks hashed
        try:
            identify_hasher(password)
            return password
        except Exception:
            return make_password(password)


# Register your models here.
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    form = ClienteAdminForm
    list_display = ('nome', 'email', 'telefone', 'estado', 'cidade', 'is_ativo', 'is_VIP', 'vip_request_pending', 'template_fatura', 'saldo_atual')
    search_fields = ('nome', 'email')
    list_filter = ('is_ativo', 'is_VIP', 'vip_request_pending', 'estado', 'cidade')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'saldo_atual', 'saldo_final')
    fieldsets = (
        (None, {
            'fields': ('nome', 'email', 'password', 'telefone', 'estado', 'cidade', 'is_ativo', 'is_VIP', 'vip_request_pending', 'template_fatura', 'pix_key', 'pix_qrcode')
        }),
        ('Diretrizes para IA', {
            'fields': ('prompt_template',),
            'classes': ('collapse',),
        }),
        ('Créditos', {
            'fields': ('valor_credito', 'saldo_atual', 'saldo_final')
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        previous_saldo = None
        if change and obj.pk:
            previous_saldo = Cliente.objects.filter(pk=obj.pk).values_list('saldo_atual', flat=True).first()

        # valor_credito é tratado como crédito a adicionar ao saldo atual
        delta = Decimal(obj.valor_credito or 0)
        base_saldo = Decimal(previous_saldo or obj.saldo_atual or 0)
        novo_saldo = base_saldo + delta
        obj.saldo_atual = novo_saldo
        obj.saldo_final = novo_saldo
        # Zera o campo de entrada para evitar reaplicar o mesmo valor em um novo save
        obj.valor_credito = Decimal('0')

        super().save_model(request, obj, form, change)
        self._sync_user(obj)

        if delta != 0:
            CreditHistory.objects.create(
                cliente=obj,
                amount=delta,
                balance_after=obj.saldo_atual,
                description='Créditos adquiridos',
            )

    def _sync_user(self, cliente: Cliente):
        user = cliente.user
        if not user:
            user = User()

        user.username = cliente.email
        user.email = cliente.email
        user.first_name = cliente.nome
        user.is_active = cliente.is_ativo

        stored_password = cliente.password
        if stored_password:
            try:
                identify_hasher(stored_password)
                user.password = stored_password
            except Exception:
                user.password = make_password(stored_password)
                cliente.password = user.password
                cliente.save(update_fields=['password'])

        user.save()

        if cliente.user_id != user.id:
            cliente.user = user
            cliente.save(update_fields=['user'])


@admin.register(ClienteContato)
class ClienteContatoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'telefone', 'cliente_display', 'created_at', 'updated_at')
    search_fields = ('nome', 'email', 'cliente__nome')
    list_filter = ('cliente',)
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Cliente De', ordering='cliente__nome')
    def cliente_display(self, obj):
        return obj.cliente


class CreditHistoryAdminForm(forms.ModelForm):
    class Meta:
        model = CreditHistory
        exclude = ('amount',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].label = 'Cliente'
        if 'balance_after' in self.fields:
            self.fields['balance_after'].label = 'Saldo após'
        self.fields['description'].label = 'Descrição'
        # Sugestões iniciais: tipo crédito e descrição PIX
        if not self.instance.pk:
            self.fields['description'].initial = 'PIX'

    def clean(self):
        cleaned = super().clean()
        if 'amount' not in self.fields:
            return cleaned
        cliente = cleaned.get('cliente')
        amount = cleaned.get('amount') or Decimal('0')
        balance_after = cleaned.get('balance_after')

        if not cleaned.get('description'):
            cleaned['description'] = 'PIX'

        if cliente:
            previous = None
            if self.instance and self.instance.pk and self.instance.balance_after is not None and self.instance.amount is not None:
                previous = Decimal(self.instance.balance_after) - Decimal(self.instance.amount)
            elif balance_after is not None and amount is not None:
                previous = Decimal(balance_after) - Decimal(amount)
            elif balance_after is None:
                previous = Decimal(cliente.valor_credito or 0)

            if previous is not None:
                cleaned['balance_after'] = previous + amount

        return cleaned


class CreatedAtFilter(admin.DateFieldListFilter):
    title = 'Criado em'


@admin.register(CreditHistory)
class CreditHistoryAdmin(admin.ModelAdmin):
    form = CreditHistoryAdminForm
    list_display = ('cliente', 'previous_balance', 'balance_display', 'description', 'created_at_display')
    list_display_links = ('cliente',)
    list_filter = (('created_at', CreatedAtFilter), 'cliente')
    search_fields = ('cliente__nome', 'description')
    readonly_fields = ('created_at', 'updated_at', 'previous_balance', 'balance_after')
    fields = ('cliente', 'previous_balance', 'balance_after', 'description', 'created_at', 'updated_at')

    @admin.display(description='Valor anterior')
    def previous_balance(self, obj):
        if obj.balance_after is None or obj.amount is None:
            return '-'
        return Decimal(obj.balance_after) - Decimal(obj.amount)

    @admin.display(description='Valor atual', ordering='balance_after')
    def balance_display(self, obj):
        return obj.balance_after

    @admin.display(description='Criado em', ordering='created_at')
    def created_at_display(self, obj):
        return obj.created_at
