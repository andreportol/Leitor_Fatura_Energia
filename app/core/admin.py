from django import forms
from django.contrib import admin
from django.contrib.auth.hashers import identify_hasher, make_password
from django.contrib.auth import get_user_model

from .models import Cliente

User = get_user_model()


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
    list_display = ('nome', 'email', 'telefone', 'estado', 'cidade', 'is_ativo', 'valor_credito', 'prompt_template', 'created_at', 'updated_at')
    search_fields = ('nome', 'email')
    list_filter = ('is_ativo', 'estado', 'cidade')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._sync_user(obj)

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
