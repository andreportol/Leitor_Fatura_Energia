from decimal import Decimal

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher, make_password
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from .models import Cliente, ClienteContato, CreditHistory

User = get_user_model()

# Branding for admin panel
logo_url = static('img/logomarca.png')
admin.site.site_header = mark_safe(f'<img src="{logo_url}" alt="ALP SISTEMAS" style="height:40px; vertical-align:middle; margin-right:8px;"> ALP SISTEMAS')
admin.site.site_title = 'ALP SISTEMAS'
admin.site.index_title = 'Painel Administrativo'


class ClienteAdminForm(forms.ModelForm):
    class Meta:
        model = Cliente
        exclude = ('user',)
        widgets = {
            'password': forms.PasswordInput(render_value=True),
        }

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
    list_display = ('nome', 'email', 'telefone', 'estado', 'cidade', 'is_ativo', 'is_VIP', 'valor_credito')
    search_fields = ('nome', 'email')
    list_filter = ('is_ativo', 'is_VIP', 'estado', 'cidade')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        previous_credit = None
        if change and obj.pk:
            previous_credit = Cliente.objects.filter(pk=obj.pk).values_list('valor_credito', flat=True).first()

        super().save_model(request, obj, form, change)
        self._sync_user(obj)

        if previous_credit is not None:
            delta = Decimal(obj.valor_credito) - Decimal(previous_credit)
            if delta != 0:
                CreditHistory.objects.create(
                    cliente=obj,
                    kind='credit' if delta > 0 else 'debit',
                    amount=delta,
                    balance_after=obj.valor_credito,
                    description='Ajuste manual no admin',
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
    list_display = ('nome', 'email', 'telefone', 'cliente', 'created_at', 'updated_at')
    search_fields = ('nome', 'email', 'cliente__nome')
    list_filter = ('cliente',)
    readonly_fields = ('created_at', 'updated_at')


class CreditHistoryAdminForm(forms.ModelForm):
    class Meta:
        model = CreditHistory
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].label = 'Cliente'
        self.fields['kind'].label = 'Tipo'
        self.fields['amount'].label = 'Valor'
        self.fields['balance_after'].label = 'Saldo após'
        self.fields['description'].label = 'Descrição'
        # Sugestões iniciais: tipo crédito e descrição PIX
        if not self.instance.pk:
            self.fields['kind'].initial = 'credit'
            self.fields['description'].initial = 'PIX'

    def clean(self):
        cleaned = super().clean()
        cliente = cleaned.get('cliente')
        amount = cleaned.get('amount') or Decimal('0')
        kind = cleaned.get('kind')
        balance_after = cleaned.get('balance_after')

        if not cleaned.get('description'):
            cleaned['description'] = 'PIX'

        if cliente and balance_after is None:
            atual = Decimal(cliente.valor_credito or 0)
            if kind == 'credit':
                cleaned['balance_after'] = atual + amount
            elif kind == 'debit':
                cleaned['balance_after'] = atual - amount

        return cleaned


class KindListFilter(admin.SimpleListFilter):
    title = 'Tipo'
    parameter_name = 'kind'

    def lookups(self, request, model_admin):
        return (
            ('credit', 'Crédito'),
            ('debit', 'Débito'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'credit':
            return queryset.filter(kind='credit')
        if self.value() == 'debit':
            return queryset.filter(kind='debit')
        return queryset


class CreatedAtFilter(admin.DateFieldListFilter):
    title = 'Criado em'


@admin.register(CreditHistory)
class CreditHistoryAdmin(admin.ModelAdmin):
    form = CreditHistoryAdminForm
    list_display = ('cliente', 'kind', 'amount', 'balance_after', 'description', 'created_at')
    list_filter = (KindListFilter, ('created_at', CreatedAtFilter), 'cliente')
    search_fields = ('cliente__nome', 'description')
    readonly_fields = ('created_at', 'updated_at')
