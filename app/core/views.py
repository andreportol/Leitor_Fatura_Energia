import io
import logging
import os
import re
import zipfile
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.hashers import identify_hasher, make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, models
from django.db import transaction
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
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from app.core.models import Cliente, ClienteContato, CreditHistory
from django.contrib.auth.password_validation import validate_password, password_validators_help_text_html
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
        try:
            from app.core.models import Cliente
            context['vip_pending_count'] = Cliente.objects.filter(vip_request_pending=True).count()
        except Exception:
            context['vip_pending_count'] = 0
        return context


class QuemSomosView(TemplateView):
    template_name = 'core/quem_somos.html'


class CadastroView(View):
    template_name = 'core/cadastro.html'
    user_model = get_user_model()

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
            'form_data': {},
            'password_help': password_validators_help_text_html(),
        })

    def post(self, request, *args, **kwargs):
        name = request.POST.get('companyName', '').strip()
        email = request.POST.get('companyEmail', '').strip()
        password = request.POST.get('companyPassword', '').strip()
        password_confirm = request.POST.get('companyPasswordConfirm', '').strip()
        state = request.POST.get('companyState', '').strip()
        city = request.POST.get('companyCity', '').strip()
        phone = request.POST.get('companyPhone', '').strip()
        # Valores padrão (não editáveis pelo formulário)
        active_flag = True
        credit_value = Decimal('0')

        form_data = {
            'companyName': name,
            'companyEmail': email,
            'companyState': state,
            'companyCity': city,
            'companyPhone': phone,
            'companyActive': active_flag,
            'companyCredit': credit_value,
        }

        if not name or not email or not phone or not password or not password_confirm or not state or not city:
            messages.error(request, 'Preencha todos os campos obrigatórios.')
            return render(request, self.template_name, {'form_data': form_data, 'password_help': password_validators_help_text_html()})

        if password != password_confirm:
            messages.error(request, 'As senhas não conferem.')
            return render(request, self.template_name, {'form_data': form_data, 'password_help': password_validators_help_text_html()})

        if Cliente.objects.filter(email=email).exists():
            messages.error(request, 'Já existe um cadastro com este e-mail.')
            return render(request, self.template_name, {'form_data': form_data, 'password_help': password_validators_help_text_html()})

        try:
            validate_password(password)
        except Exception as exc:
            messages.error(request, '; '.join(exc.messages) if hasattr(exc, 'messages') else 'Senha inválida.')
            return render(request, self.template_name, {'form_data': form_data, 'password_help': password_validators_help_text_html()})

        try:
            with transaction.atomic():
                user = self.user_model(username=email, email=email, first_name=name, is_active=active_flag)
                user.set_password(password)
                user.save()

                cliente = Cliente.objects.create(
                    user=user,
                    nome=name,
                    email=email,
                    telefone=phone or None,
                    estado=state,
                    cidade=city,
                    is_ativo=active_flag,
                    is_VIP=False,
                    valor_credito=credit_value,
                    password=user.password,  # hashed
                )
        except IntegrityError:
            messages.error(request, 'Não foi possível concluir o cadastro. Verifique os dados e tente novamente.')
            return render(request, self.template_name, {'form_data': form_data, 'password_help': password_validators_help_text_html()})

        login(request, user)
        request.session['cliente_id'] = cliente.id
        request.session['cliente_nome'] = cliente.nome
        messages.success(request, 'Bem-vindo à área de processamento de faturas. Adquira créditos e processe suas faturas de forma rápida e automática.')
        return redirect('core:processamento')

class ContatoCrudView(LoginRequiredMixin, TemplateView):
    template_name = 'core/contatos.html'
    login_url = 'core:login'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        cliente = getattr(request.user, 'cliente', None)
        if not cliente or not cliente.is_VIP:
            messages.error(request, 'Área restrita a clientes VIP.')
            return redirect('core:processamento')
        request.session['cliente_id'] = cliente.id
        request.session['cliente_nome'] = cliente.nome
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        cliente = getattr(request.user, 'cliente', None)
        if not cliente or not cliente.is_VIP:
            messages.error(request, 'Área restrita a clientes VIP.')
            return redirect('core:processamento')

        action = request.POST.get('action')
        if action == 'save_contact':
            return self._handle_save_contact(request, cliente)
        if action == 'delete_contact':
            return self._handle_delete_contact(request, cliente)

        messages.error(request, 'Ação inválida.')
        return redirect('core:contatos')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = getattr(self.request.user, 'cliente', None)
        context['cliente'] = cliente
        search = self.request.GET.get('contact_q', '').strip()
        contatos_qs = cliente.contatos.all()
        if search:
            contatos_qs = contatos_qs.filter(models.Q(nome__icontains=search) | models.Q(email__icontains=search))
        contatos_qs = contatos_qs.order_by('nome')
        paginator = Paginator(contatos_qs, 10)
        page = self.request.GET.get('page') or 1
        try:
            page_obj = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        context['contatos'] = list(page_obj.object_list)
        context['contact_search'] = search
        context['contacts_total'] = paginator.count
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        return context

    def _handle_save_contact(self, request, cliente):
        contact_id = request.POST.get('contact_id')
        nome = request.POST.get('contact_name', '').strip()
        email = request.POST.get('contact_email', '').strip()
        telefone = request.POST.get('contact_phone', '').strip()

        if not nome:
            messages.error(request, 'Informe o nome do contato.')
            return redirect('core:contatos')

        if not email and not telefone:
            messages.error(request, 'Informe e-mail ou telefone para o contato.')
            return redirect('core:contatos')

        if contact_id:
            contato = ClienteContato.objects.filter(pk=contact_id, cliente=cliente).first()
            if not contato:
                messages.error(request, 'Contato não encontrado.')
                return redirect('core:contatos')
        else:
            contato = ClienteContato(cliente=cliente)

        contato.nome = nome
        contato.email = email or None
        contato.telefone = telefone or None
        try:
            contato.save()
        except Exception as exc:
            logger.exception('Erro ao salvar contato VIP')
            messages.error(request, f'Não foi possível salvar o contato: {exc}')
            return redirect('core:contatos')

        messages.success(request, 'Contato salvo com sucesso.')
        return redirect('core:contatos')

    def _handle_delete_contact(self, request, cliente):
        contact_id = request.POST.get('contact_id')
        contato = ClienteContato.objects.filter(pk=contact_id, cliente=cliente).first()
        if not contato:
            messages.error(request, 'Contato não encontrado.')
            return redirect('core:contatos')

        contato.delete()
        messages.success(request, 'Contato removido.')
        return redirect('core:contatos')


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
        lock_until = datetime.fromtimestamp(lock_until_ts, tz=dt_timezone.utc)
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
        if action == 'save_contact':
            return self._handle_save_contact(request, cliente)
        if action == 'delete_contact':
            return self._handle_delete_contact(request, cliente)
        if action == 'send_invoice':
            return self._handle_send_invoice(request, cliente)
        if action == 'send_all':
            return self._handle_send_all(request, cliente)
        if action == 'request_vip_upgrade':
            return self._handle_request_vip_upgrade(request, cliente)

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

        credit_available = Decimal(getattr(cliente, 'saldo_atual', None) or 0)
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
                nome_para_arquivo = context.get('cliente', {}).get('nome') or getattr(cliente, 'nome', '')
                raw_file_name = Path(f.name).name or 'fatura.pdf'
                outputs.append((Path(f.name).stem or 'fatura', html, nome_para_arquivo, raw_file_name))
            except Exception as exc:
                logger.exception('Erro ao processar fatura %s', f.name)
                messages.error(request, f'Erro ao processar {f.name}: {exc}')

        if not outputs:
            return redirect('core:processamento')

        processed = []
        contatos_cache = list(ClienteContato.objects.filter(cliente=cliente)) if cliente.is_VIP else []
        for idx, (name, html, nome_para_arquivo, raw_file_name) in enumerate(outputs, start=1):
            if cliente.is_VIP:
                base_name = Path(raw_file_name).stem or (slugify(nome_para_arquivo) or slugify(cliente.nome) or 'cliente')
                safe_name = base_name
                contact_match = self._match_contact_by_name(contatos_cache, nome_para_arquivo)
            else:
                safe_name = Path(raw_file_name).stem or (slugify(name) or 'fatura')
                contact_match = None
            processed.append({
                'name': f'{safe_name}.html',
                'content': html,
                'status': 'processado',
                'contact_name': nome_para_arquivo,
                'suggested_contact_id': contact_match.id if contact_match else None,
                'suggested_contact_name': contact_match.nome if contact_match else '',
                'original_name': raw_file_name,
            })

        # Debita os créditos apenas pelas faturas geradas
        try:
            debit = Decimal(len(processed))
            cliente.saldo_atual = (credit_available - debit)
            cliente.saldo_final = cliente.saldo_atual
            cliente.valor_credito = Decimal('0')
            cliente.save(update_fields=['saldo_atual', 'saldo_final', 'valor_credito'])
            CreditHistory.objects.create(
                cliente=cliente,
                amount=-debit,
                balance_after=cliente.saldo_atual,
                description=f'Débito por processamento de {len(processed)} fatura(s)',
            )
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
        context['is_vip'] = bool(getattr(cliente, 'is_VIP', False))
        if getattr(cliente, 'is_VIP', False):
            contatos_lista = list(cliente.contatos.order_by('nome'))
            context['contatos'] = contatos_lista
            context['contacts_total'] = len(contatos_lista)
        else:
            context['contatos'] = []
            context['contacts_total'] = 0
        if processed and getattr(cliente, 'is_VIP', False):
            contatos_lista = context.get('contatos') or []

            def _to_int(value):
                if value is None:
                    return None
                if isinstance(value, str):
                    value = value.strip()
                if value == '':
                    return None
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

            for item in processed:
                resolved_id = None
                suggested_id = _to_int(item.get('suggested_contact_id'))
                contact_id = _to_int(item.get('contact_id')) or suggested_id
                candidate_ids = [cid for cid in (contact_id, suggested_id) if cid]

                for cid in candidate_ids:
                    match = next((c for c in contatos_lista if c.id == cid), None)
                    if match:
                        resolved_id = match.id
                        item['resolved_contact_phone'] = match.telefone
                        phone_digits = re.sub(r'\D+', '', match.telefone or '')
                        if phone_digits:
                            item['resolved_whatsapp_link'] = f'https://wa.me/{phone_digits}'
                        break

                if not resolved_id:
                    search_order = [
                        item.get('suggested_contact_name') or '',
                        item.get('contact_name') or '',
                    ]
                    for candidate in search_order:
                        if not candidate or resolved_id:
                            continue
                        match = self._match_contact_by_name(contatos_lista, candidate)
                        if match:
                            resolved_id = match.id
                            item['resolved_contact_phone'] = match.telefone
                            phone_digits = re.sub(r'\D+', '', match.telefone or '')
                            if phone_digits:
                                item['resolved_whatsapp_link'] = f'https://wa.me/{phone_digits}'
                            break

                item['resolved_contact_id'] = resolved_id
                item['has_contact'] = bool(resolved_id)
                item.setdefault('resolved_contact_phone', '')
                item.setdefault('resolved_whatsapp_link', '')
            context['processed_files'] = processed
        if cliente:
            history_qs = cliente.credit_history.all().order_by('-created_at')
            paginator = Paginator(history_qs, 10)
            page_number = self.request.GET.get('history_page') or 1
            try:
                history_page = paginator.page(page_number)
            except (PageNotAnInteger, EmptyPage):
                history_page = paginator.page(1)

            history = []
            for entry in history_page.object_list:
                previous = None
                if entry.balance_after is not None and entry.amount is not None:
                    previous = Decimal(entry.balance_after) - Decimal(entry.amount)
                history.append({'entry': entry, 'previous': previous})

            context['credit_history'] = history
            context['credit_history_page'] = history_page
        else:
            context['credit_history'] = []
            context['credit_history_page'] = None

        last_link = self.request.session.pop('last_whatsapp_link', '')
        if last_link:
            self.request.session.modified = True
        context['last_whatsapp_link'] = last_link
        return context

    def _get_processed_files(self, request):
        return request.session.get('processed_files', [])

    def _set_processed_files(self, request, files):
        request.session['processed_files'] = files
        request.session.modified = True

    # --------------------------- VIP: Contatos + envio ----------------------
    def _handle_save_contact(self, request, cliente):
        if not cliente.is_VIP:
            messages.error(request, 'Somente clientes VIP podem gerenciar contatos.')
            return redirect('core:processamento')

        contact_id = request.POST.get('contact_id')
        nome = request.POST.get('contact_name', '').strip()
        email = request.POST.get('contact_email', '').strip()
        telefone = request.POST.get('contact_phone', '').strip()

        if not nome:
            messages.error(request, 'Informe o nome do contato.')
            return redirect('core:processamento')

        if not email and not telefone:
            messages.error(request, 'Informe e-mail ou telefone para o contato.')
            return redirect('core:processamento')

        if contact_id:
            contato = ClienteContato.objects.filter(pk=contact_id, cliente=cliente).first()
            if not contato:
                messages.error(request, 'Contato não encontrado.')
                return redirect('core:processamento')
        else:
            contato = ClienteContato(cliente=cliente)

        contato.nome = nome
        contato.email = email or None
        contato.telefone = telefone or None
        try:
            contato.save()
        except Exception as exc:
            logger.exception('Erro ao salvar contato VIP')
            messages.error(request, f'Não foi possível salvar o contato: {exc}')
            return redirect('core:processamento')

        messages.success(request, 'Contato salvo com sucesso.')
        return redirect('core:processamento')

    def _handle_delete_contact(self, request, cliente):
        if not cliente.is_VIP:
            messages.error(request, 'Somente clientes VIP podem gerenciar contatos.')
            return redirect('core:processamento')

        contact_id = request.POST.get('contact_id')
        contato = ClienteContato.objects.filter(pk=contact_id, cliente=cliente).first()
        if not contato:
            messages.error(request, 'Contato não encontrado.')
            return redirect('core:processamento')

        contato.delete()
        messages.success(request, 'Contato removido.')
        return redirect('core:processamento')

    def _handle_send_invoice(self, request, cliente):
        is_ajax = request.headers.get('x-requested-with', '').lower() == 'xmlhttprequest'

        def ajax_error(msg, status=400):
            if is_ajax:
                return JsonResponse({'success': False, 'message': msg}, status=status)
            messages.error(request, msg)
            return redirect('core:processamento')

        def ajax_success(msg='Fatura enviada.', whatsapp_link=''):
            if is_ajax:
                return JsonResponse({'success': True, 'message': msg, 'whatsapp_link': whatsapp_link or ''})
            messages.success(request, msg)
            return redirect('core:processamento')

        if not cliente.is_VIP:
            return ajax_error('Somente clientes VIP podem enviar faturas automaticamente.', status=403)

        contact_id_raw = request.POST.get('contact_id', '').strip()
        contact_name_input = request.POST.get('contact_name', '').strip()
        file_index_raw = request.POST.get('file_index', '0')
        processed = self._get_processed_files(request)

        if not processed:
            return ajax_error('Não há fatura processada para enviar.')

        try:
            file_index = int(file_index_raw)
        except ValueError:
            file_index = 0

        if file_index < 0 or file_index >= len(processed):
            return ajax_error('Fatura selecionada é inválida.')

        def _to_int(value):
            if value is None:
                return None
            if isinstance(value, str):
                value = value.strip()
            if value == '':
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        suggested_id = _to_int(processed[file_index].get('suggested_contact_id'))
        suggested_name = processed[file_index].get('suggested_contact_name') or ''
        invoice_contact_name = processed[file_index].get('contact_name', '')
        contact_id = _to_int(contact_id_raw) or suggested_id
        contatos_qs = ClienteContato.objects.filter(cliente=cliente)

        contato = None
        candidate_ids = [cid for cid in (contact_id, suggested_id) if cid]
        if candidate_ids:
            contato = contatos_qs.filter(pk__in=candidate_ids).first()

        if not contato:
            search_order = [contact_name_input, suggested_name, invoice_contact_name]
            for candidate in search_order:
                if not candidate or contato:
                    continue
                contato = contatos_qs.filter(nome__iexact=candidate).first()
                if not contato:
                    contato = contatos_qs.filter(nome__icontains=candidate).first()

        if not contato:
            return ajax_error('Contato não encontrado. Busque pelo nome ou cadastre antes de enviar.')

        item = processed[file_index]
        success, whatsapp_link = self._send_invoice_to_contact(contato, item, cliente)
        if success:
            request.session.modified = True
            return ajax_success('Fatura enviada para o contato.', whatsapp_link=whatsapp_link)
        return ajax_error('Não foi possível enviar a fatura. Verifique o contato.')

    def _handle_send_all(self, request, cliente):
        if not cliente.is_VIP:
            messages.error(request, 'Somente clientes VIP podem enviar faturas automaticamente.')
            return redirect('core:processamento')

        processed = self._get_processed_files(request)
        if not processed:
            messages.error(request, 'Não há faturas processadas para enviar.')
            return redirect('core:processamento')

        contatos_cache = list(ClienteContato.objects.filter(cliente=cliente))
        success = 0
        skipped = 0
        for item in processed:
            contato = None
            if item.get('suggested_contact_id'):
                contato = next((c for c in contatos_cache if c.id == item['suggested_contact_id']), None)
            if not contato:
                contato = self._match_contact_by_name(contatos_cache, item.get('contact_name', ''))
            if not contato:
                skipped += 1
                continue
            sent, _ = self._send_invoice_to_contact(contato, item, cliente)
            if sent:
                success += 1

        if success:
            messages.success(request, f'{success} fatura(s) enviada(s) automaticamente.')
        if skipped:
            messages.info(request, f'{skipped} fatura(s) sem correspondência de contato. Use a busca para enviar manualmente.')
        if not success and not skipped:
            messages.info(request, 'Nenhuma fatura enviada.')
        request.session.modified = True
        return redirect('core:processamento')

    def _match_contact_by_name(self, contatos_cache, nome_busca: str):
        if not nome_busca:
            return None
        alvo_slug = slugify(nome_busca).replace('-', '')
        alvo_lower = nome_busca.lower().strip()
        for c in contatos_cache:
            ref = slugify(c.nome).replace('-', '')
            if ref == alvo_slug:
                return c
        for c in contatos_cache:
            if c.nome.lower().strip() == alvo_lower:
                return c
        for c in contatos_cache:
            if alvo_lower and alvo_lower in c.nome.lower():
                return c
        return None

    def _send_invoice_to_contact(self, contato: ClienteContato, item, cliente: Cliente):
        file_name = item.get('name', 'fatura.html')
        html_body = item.get('content', '')

        email_sent = False
        whatsapp_link = ''
        if contato.email:
            try:
                subject = f'Fatura | {cliente.nome}'
                body_txt = (
                    f'Olá {contato.nome},\n\n'
                    f'Segue a fatura processada do cliente {cliente.nome}.\n'
                    f'Este e-mail foi enviado automaticamente pelo painel VIP.'
                )
                email_message = EmailMessage(
                    subject=subject,
                    body=body_txt,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[contato.email],
                )
                email_message.attach(file_name, html_body, 'text/html')
                email_message.send(fail_silently=False)
                email_sent = True
            except Exception as exc:
                logger.exception('Erro ao enviar fatura por e-mail para contato %s', contato.id)
                messages.error(self.request, f'Não foi possível enviar o e-mail para {contato.nome}: {exc}')
                return False, ''

        telefone_digits = re.sub(r'\D+', '', contato.telefone or '')
        if telefone_digits:
            mensagem = (
                f'Olá {contato.nome}, segue a fatura do cliente {cliente.nome}. '
                f'O arquivo foi enviado para seu e-mail: {contato.email or "sem e-mail cadastrado"}.'
            )
            whatsapp_link = f'https://wa.me/{telefone_digits}?text={quote(mensagem)}'

        if whatsapp_link:
            msg = 'Clique no botão do WhatsApp para completar o envio.'
            if email_sent:
                msg = 'Fatura enviada por e-mail. ' + msg
            messages.success(self.request, msg)
            self.request.session['last_whatsapp_link'] = whatsapp_link
        elif email_sent:
            messages.success(self.request, f'Fatura enviada por e-mail para {contato.nome}.')
        else:
            messages.info(self.request, 'Nenhum e-mail cadastrado para envio automático. Adicione um e-mail ou telefone.')

        return True, whatsapp_link

    def _handle_request_vip_upgrade(self, request, cliente):
        if cliente.is_VIP:
            messages.info(request, 'Você já é cliente VIP.')
            return redirect('core:processamento')

        if cliente.vip_request_pending:
            messages.info(request, 'Sua solicitação de upgrade já foi recebida. Entraremos em contato em breve.')
            return redirect('core:processamento')

        cliente.vip_request_pending = True
        cliente.save(update_fields=['vip_request_pending'])
        messages.success(
            request,
            'Recebemos seu interesse em se tornar VIP! Em breve entraremos em contato para definir layout, data e forma de pagamento e demais detalhes.'
        )
        # Mantém um alerta simples para administradores: aparece no admin via campo "vip_request_pending".
        return redirect('core:processamento')


class LogoutView(View):
    def post(self, request, *args, **kwargs):
        logout(request)
        request.session.pop('login_attempts', None)
        request.session.pop('login_lock_until', None)
        request.session.pop('cliente_id', None)
        request.session.pop('cliente_nome', None)
        request.session.modified = True
        return redirect('core:login')
