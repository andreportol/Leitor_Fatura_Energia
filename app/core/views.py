import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.hashers import identify_hasher, make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.core.mail import EmailMessage, send_mail
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from app.core.models import Cliente

logger = logging.getLogger(__name__)


# Create your views here.
class TemplateViewsIndex(TemplateView):
    template_name = 'core/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        whatsapp_number = getattr(settings, 'WHATSAPP_NUMBER', '').strip()
        whatsapp_url = ''
        if whatsapp_number:
            whatsapp_url = f'https://wa.me/{whatsapp_number}?text=Ol%C3%A1%20ALP%20SISTEMAS'
        context['whatsapp_url'] = whatsapp_url
        return context


class QuemSomosView(TemplateView):
    template_name = 'core/quem_somos.html'


class CadastroView(TemplateView):
    template_name = 'core/cadastro.html'


class ContactFormView(View):
    def post(self, request, *args, **kwargs):
        name = request.POST.get('name', '').strip()
        company = request.POST.get('company', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        message = request.POST.get('message', '').strip()

        if not name or not email or not message:
            return JsonResponse(
                {'success': False, 'error': 'Preencha nome, e-mail e mensagem.'},
                status=400,
            )

        # Destinatário fixo para leitura das mensagens
        recipient = getattr(settings, 'CONTACT_EMAIL', None) or 'alpsistemascg@gmail.com'
        if not recipient:
            return JsonResponse(
                {'success': False, 'error': 'Destinatário não configurado.'},
                status=500,
            )

        subject = f'Nova mensagem - ALP SISTEMAS | {name}'
        body = (
            f'Nome: {name}\n'
            f'Empresa: {company}\n'
            f'E-mail: {email}\n'
            f'Telefone: {phone}\n\n'
            f'Mensagem:\n{message}'
        )

        try:
            email_message = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
                reply_to=[email] if email else None,
            )
            email_message.send(fail_silently=False)
        except Exception as exc:
            logger.exception('Falha ao enviar e-mail de contato')
            error_msg = 'Não foi possível enviar o e-mail. Verifique as credenciais do remetente.'
            if settings.DEBUG:
                error_msg = f'{error_msg} Detalhe: {exc}'
            return JsonResponse({'success': False, 'error': error_msg}, status=500)

        return JsonResponse({'success': True})


class LoginView(View):
    template_name = 'core/login.html'
    max_attempts = 3
    lock_minutes = 3
    user_model = get_user_model()

    def _get_lock_remaining_seconds(self, request):
        lock_until_ts = request.session.get('login_lock_until')
        if not lock_until_ts:
            return 0

        now = timezone.now()
        lock_until = timezone.datetime.fromtimestamp(lock_until_ts, tz=timezone.utc)
        remaining = (lock_until - now).total_seconds()
        if remaining <= 0:
            self._clear_lockout(request)
            return 0
        return int(remaining)

    def _clear_lockout(self, request):
        request.session.pop('login_attempts', None)
        request.session.pop('login_lock_until', None)
        request.session.modified = True

    def _ensure_user(self, cliente: Cliente):
        user = cliente.user
        if not user:
            user = self.user_model()

        user.username = cliente.email
        user.email = cliente.email
        user.first_name = cliente.nome
        user.is_active = cliente.is_ativo

        stored_password = cliente.password or ''
        if stored_password:
            try:
                identify_hasher(stored_password)
                user.password = stored_password
            except Exception:
                user.set_password(stored_password)
                cliente.password = user.password
                cliente.save(update_fields=['password'])

        user.save()

        if cliente.user_id != user.id:
            cliente.user = user
            cliente.save(update_fields=['user'])

        return user

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.session.get('cliente_id'):
            return redirect('core:processamento')
        lockout_remaining_seconds = self._get_lock_remaining_seconds(request)
        return render(
            request,
            self.template_name,
            {'lockout_remaining_seconds': lockout_remaining_seconds},
        )

    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        lockout_remaining_seconds = self._get_lock_remaining_seconds(request)
        if lockout_remaining_seconds:
            return render(
                request,
                self.template_name,
                {
                    'error_message': 'Muitas tentativas. Aguarde para tentar novamente.',
                    'lockout_remaining_seconds': lockout_remaining_seconds,
                },
            )

        if not email or not password:
            return render(
                request,
                self.template_name,
                {'error_message': 'Informe e-mail e senha para continuar.'},
            )

        cliente = Cliente.objects.filter(
            email=email,
            is_ativo=True,
        ).first()

        if cliente:
            self._ensure_user(cliente)
            user = authenticate(request, username=cliente.email, password=password)
            if user:
                self._clear_lockout(request)
                login(request, user)
                request.session['cliente_id'] = cliente.id
                request.session['cliente_nome'] = cliente.nome
                redirect_url = reverse('core:processamento')
                return redirect(redirect_url)

        attempts = request.session.get('login_attempts', 0) + 1
        request.session['login_attempts'] = attempts
        request.session.modified = True

        if attempts >= self.max_attempts:
            lock_until = timezone.now() + timedelta(minutes=self.lock_minutes)
            request.session['login_lock_until'] = lock_until.timestamp()
            request.session['login_attempts'] = 0
            request.session.modified = True
            lockout_remaining_seconds = self._get_lock_remaining_seconds(request)
            return render(
                request,
                self.template_name,
                {
                    'error_message': 'Número máximo de tentativas atingido. '
                                     'Aguarde para tentar novamente.',
                    'lockout_remaining_seconds': lockout_remaining_seconds,
                },
            )

        return render(
            request,
            self.template_name,
            {
                'error_message': f'E-mail ou senha incorretos. '
                                 f'Tentativa {attempts} de {self.max_attempts}.',
                'lockout_remaining_seconds': self._get_lock_remaining_seconds(request),
            },
        )


class ProcessamentoView(LoginRequiredMixin, TemplateView):
    template_name = 'core/processamento.html'
    login_url = 'core:login'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        cliente = getattr(request.user, 'cliente', None)
        if not cliente:
            logout(request)
            return redirect('core:login')

        request.session['cliente_id'] = cliente.id
        request.session['cliente_nome'] = cliente.nome
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        cliente = getattr(request.user, 'cliente', None)
        if not cliente:
            logout(request)
            return redirect('core:login')

        action = request.POST.get('action')
        if action == 'update_profile':
            return self._handle_update_profile(request, cliente)
        if action == 'update_prompt':
            return self._handle_update_prompt(request, cliente)

        messages.error(request, 'Ação inválida.')
        return redirect('core:processamento')

    def _handle_update_profile(self, request, cliente):
        email = request.POST.get('email', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        estado = request.POST.get('estado', '').strip()
        cidade = request.POST.get('cidade', '').strip()
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()

        if not email:
            messages.error(request, 'E-mail é obrigatório.')
            return redirect('core:processamento')

        if Cliente.objects.filter(email=email).exclude(pk=cliente.pk).exists():
            messages.error(request, 'Este e-mail já está em uso por outro cliente.')
            return redirect('core:processamento')

        if password and password != password_confirm:
            messages.error(request, 'A confirmação de senha não confere.')
            return redirect('core:processamento')

        cliente.email = email
        cliente.telefone = telefone
        cliente.estado = estado
        cliente.cidade = cidade

        user = request.user
        user.email = email
        user.username = email
        user.first_name = cliente.nome

        if password:
            user.set_password(password)
            cliente.password = user.password

        try:
            user.save()
            cliente.save()
            if password:
                update_session_auth_hash(request, user)
        except IntegrityError:
            messages.error(request, 'Não foi possível atualizar. Verifique os dados e tente novamente.')
            return redirect('core:processamento')

        request.session['cliente_nome'] = cliente.nome
        messages.success(request, 'Dados atualizados com sucesso.')
        return redirect('core:processamento')

    def _handle_update_prompt(self, request, cliente):
        prompt = request.POST.get('prompt_template', '').strip()
        cliente.prompt_template = prompt
        cliente.save(update_fields=['prompt_template'])
        messages.success(request, 'Diretrizes para IA atualizadas com sucesso.')
        return redirect('core:processamento')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = getattr(self.request.user, 'cliente', None)
        context['cliente'] = cliente
        context['cliente_nome'] = self.request.session.get('cliente_nome', '') or getattr(self.request.user, 'first_name', '')
        return context


class LogoutView(View):
    def post(self, request, *args, **kwargs):
        logout(request)
        request.session.pop('login_attempts', None)
        request.session.pop('login_lock_until', None)
        request.session.pop('cliente_id', None)
        request.session.pop('cliente_nome', None)
        request.session.modified = True
        return redirect('core:login')
