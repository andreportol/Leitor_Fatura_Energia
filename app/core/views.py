import io
import logging
import os
import re
import zipfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.hashers import identify_hasher, make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.core.mail import EmailMessage
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import TemplateView

from app.core.models import Cliente
from app.core.processamento import processar_pdf

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
        if action == 'process_files':
            return self._handle_process_files(request, cliente)
        if action == 'download_file':
            return self._handle_download_file(request)
        if action == 'download_all':
            return self._handle_download_all(request)

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

    def _absolute_static(self, path: str) -> str:
        """Retorna URL absoluta para um arquivo estático, preferindo a versão com hash."""
        try:
            url = staticfiles_storage.url(path)
        except Exception:
            url = f"{settings.STATIC_URL}{path}" if settings.STATIC_URL else ''
        return self.request.build_absolute_uri(url) if url else ''

    def _build_historico(self, historico_raw):
        historico = []
        for item in historico_raw or []:
            consumo = (item or {}).get('consumo', '')
            mes = (item or {}).get('mes', '')
            historico.append(
                {
                    'rotulo': mes,
                    'consumo_display': consumo or 'N/A',
                    'has_consumo': bool(consumo),
                }
            )
        return historico

    def _fallback_consumo_atual(self, data):
        """Tenta obter consumo atual; se vazio, usa primeiro valor do histórico."""
        consumo = data.get('consumo_kwh') or data.get('consumo kwh', '')
        if consumo:
            return consumo
        for item in data.get('historico_de_consumo') or data.get('historico de consumo') or []:
            if not item:
                continue
            valor = item.get('consumo') or item.get('consumo kwh')
            if valor:
                return valor
        return ''

    def _simplify_endereco(self, endereco: str) -> str:
        """
        Remove partes detalhadas (ex.: quadra/lote) para deixar o endereÇõo mais limpo.
        Exemplo: "RUA X, 123 - QD 58 LT 04 - 08 103 37 362000 - 79094550 Y"
        vira "RUA X, 123 - 79094550 Y".
        """
        if not endereco:
            return ''

        parts = [p.strip() for p in endereco.split('-')]
        filtered = []
        for part in parts:
            if not part:
                continue
            upper = part.upper()
            if any(tag in upper for tag in ('QD', 'QUADRA', 'LT', 'LOTE')):
                continue
            if re.fullmatch(r'[\d\s]+', part):
                continue
            filtered.append(part)

        cleaned = ' - '.join(filtered)
        cleaned = re.sub(r'\s*\([^)]*\)', '', cleaned)  # remove parenteses extras (ex.: AG: 103)
        cleaned = ' '.join(cleaned.split())
        return cleaned.strip(' -')

    def _build_invoice_context(self, data, cliente):
        historico_raw = data.get('historico_de_consumo') or data.get('historico de consumo')
        historico_consumo = self._build_historico(historico_raw)
        consumo_atual = self._fallback_consumo_atual(data)
        nome_cliente = data.get('nome_do_cliente') or data.get('nome do cliente', '')
        codigo_uc = data.get('codigo_do_cliente_uc') or data.get('codigo do cliente - uc', '')
        endereco = self._simplify_endereco(data.get('endereco', ''))
        data_emissao = data.get('data_de_emissao') or data.get('data de emissao', '')
        data_vencimento = data.get('data_de_vencimento') or data.get('data de vencimento', '')
        valor_a_pagar = data.get('valor_a_pagar') or data.get('valor a pagar', '')
        economia = data.get('economia') or data.get('Economia', '')
        energia_injetada = data.get('energia_atv_injetada_kwh') or data.get('Energia Atv Injetada', '')
        preco_unitario = data.get('preco_unitario') or data.get('preco unit com tributos', '')
        saldo_acumulado = data.get('saldo_acumulado') or data.get('saldo acumulado', '')
        mes_referencia = data.get('mes_referencia') or data.get('mes de referencia', '')
        leitura_anterior = data.get('leitura_anterior') or data.get('leitura anterior', '')
        pix_key = getattr(settings, 'PIX_KEY', 'alpsistemascg@gmail.com')
        leitura_atual = data.get('leitura_atual') or data.get('leitura atual', '')
        return {
            'logo_path': self._absolute_static('img/logomarca.png'),
            'qrcode_path': self._absolute_static('img/qrcode_bancobrasil.jpeg'),
            'pix_key': pix_key,
            'mes_referencia': mes_referencia,
            'cliente': {
                'nome': nome_cliente or getattr(cliente, 'nome', ''),
                'codigo_uc': codigo_uc,
                'endereco': endereco,
            },
            'fatura': {
                'data_emissao': data_emissao,
                'data_vencimento': data_vencimento,
                'saldo_acumulado_display': saldo_acumulado,
                'valor_total_display': valor_a_pagar,
                'leitura_anterior': leitura_anterior,
                'leitura_atual': leitura_atual,
                'codigo_barras': '',
            },
            'economia_display': economia,
            'consumo_atual': consumo_atual,
            'energia_ativa_display': energia_injetada,
            'preco_unitario_display': preco_unitario,
            'historico_consumo': historico_consumo,
            'historico_resumo': '',
        }

    def _handle_process_files(self, request, cliente):
        files = request.FILES.getlist('invoice_files')
        if not files:
            messages.error(request, 'Envie pelo menos um PDF para processar.')
            return redirect('core:processamento')

        api_key = os.getenv('OPENAI_API_KEY', '').strip()
        if not api_key:
            messages.error(request, 'Defina a variável OPENAI_API_KEY para processar faturas.')
            return redirect('core:processamento')

        credit_available = Decimal(cliente.valor_credito or 0)
        file_count = len(files)
        if credit_available < file_count:
            max_allowed = int(credit_available)
            if max_allowed > 0:
                messages.error(
                    request,
                    f'Crédito insuficiente para {file_count} faturas. '
                    f'Você pode enviar no máximo {max_allowed} fatura(s) com o saldo atual.'
                )
            else:
                messages.error(
                    request,
                    'Crédito insuficiente. Adquira créditos para processar novas faturas.'
                )
            return redirect('core:processamento')

        outputs = []
        for f in files:
            try:
                parsed = processar_pdf(f)
                context = self._build_invoice_context(parsed, cliente)
                html = render_to_string('core/modelo_fatura.html', context)
                outputs.append((Path(f.name).stem or 'fatura', html))
            except Exception as exc:
                logger.exception('Erro ao processar fatura %s', f.name)
                messages.error(request, f'Erro ao processar {f.name}: {exc}')

        if not outputs:
            return redirect('core:processamento')

        processed = []
        for name, html in outputs:
            safe_name = slugify(name) or 'fatura'
            processed.append({
                'name': f'{safe_name}.html',
                'content': html,
                'status': 'processado',
            })

        # Debita os créditos apenas pelas faturas geradas
        try:
            debit = Decimal(len(processed))
            cliente.valor_credito = (credit_available - debit)
            cliente.save(update_fields=['valor_credito'])
        except Exception:
            logger.exception('Falha ao debitar créditos do cliente %s', cliente.id)

        self._set_processed_files(request, processed)
        messages.success(request, f'{len(processed)} fatura(s) pronta(s) para download.')
        return redirect('core:processamento')

    def _handle_download_file(self, request):
        processed = self._get_processed_files(request)
        try:
            idx = int(request.POST.get('file_index', '0'))
        except ValueError:
            messages.error(request, 'Arquivo inválido.')
            return redirect('core:processamento')

        if idx < 0 or idx >= len(processed):
            messages.error(request, 'Arquivo não encontrado na lista processada.')
            return redirect('core:processamento')

        item = processed[idx]
        # Limpa após o download para ocultar o card
        self._set_processed_files(request, [])
        response = HttpResponse(item.get('content', ''), content_type='text/html')
        response['Content-Disposition'] = f'attachment; filename="{item.get("name", "fatura.html")}"'
        return response

    def _handle_download_all(self, request):
        processed = self._get_processed_files(request)
        if not processed:
            messages.error(request, 'Não há faturas processadas para baixar.')
            return redirect('core:processamento')

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for item in processed:
                zf.writestr(item.get('name', 'fatura.html'), item.get('content', ''))
        buffer.seek(0)

        # Limpa após o download zipado para ocultar o card
        self._set_processed_files(request, [])

        response = HttpResponse(buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="faturas.zip"'
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = getattr(self.request.user, 'cliente', None)
        context['cliente'] = cliente
        context['cliente_nome'] = self.request.session.get('cliente_nome', '') or getattr(self.request.user, 'first_name', '')
        processed = self._get_processed_files(self.request)
        context['processed_files'] = processed
        context['has_processed_files'] = bool(processed)
        return context

    def _get_processed_files(self, request):
        return request.session.get('processed_files', [])

    def _set_processed_files(self, request, files):
        request.session['processed_files'] = files
        request.session.modified = True


class LogoutView(View):
    def post(self, request, *args, **kwargs):
        logout(request)
        request.session.pop('login_attempts', None)
        request.session.pop('login_lock_until', None)
        request.session.pop('cliente_id', None)
        request.session.pop('cliente_nome', None)
        request.session.modified = True
        return redirect('core:login')
