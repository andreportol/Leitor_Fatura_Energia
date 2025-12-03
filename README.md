# Leitor de Fatura de Energia

Aplicação Django para cadastro de clientes, autenticação e painel onde o usuário atualiza dados e envia faturas em PDF para processamento assistido por IA. Inclui painel administrativo estilizado com Jazzmin e está pronta para rodar com SQLite (desenvolvimento) ou PostgreSQL (produção).

## Principais funcionalidades
- Landing page com apresentação do serviço e formulário de contato com envio de e-mail.
- Autenticação de clientes com proteção contra tentativas excessivas de login.
- Painel do cliente para atualizar dados, senha, instruções (prompt) usadas na extração e visualizar créditos.
- Interface administrativa (`/admin`) para gerenciar clientes, sincronizando credenciais automaticamente com o modelo de usuário do Django.
- Pronta para servir arquivos estáticos com WhiteNoise e execução com Gunicorn (Procfile incluso).

## Requisitos
- Python 3.10 (vide `runtime.txt`).
- Pip e virtualenv.
- Opcional: PostgreSQL (para produção); SQLite é usado por padrão se nenhuma variável de banco for definida.

## Estrutura do projeto (resumo)
- `LEITOR_FATURA/`: configurações do Django (`settings.py`, `urls.py`, `wsgi.py`).
- `app/core/`: views, modelos (`Cliente`), templates e assets estáticos.
- `app/dashboard/`: app reservado para dashboards futuros.
- `manage.py`: utilitário para comandos do Django.
- `requirements.txt`, `Procfile`, `runtime.txt`.

## Passo a passo para rodar localmente
1. **Criar e ativar o ambiente virtual**
   ```bash
   python -m venv .venv
   source .venv/bin/activate         # Linux/macOS
   # .venv\Scripts\activate          # Windows PowerShell
   ```
2. **Instalar dependências**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. **Configurar variáveis de ambiente**  
   Crie um arquivo `.env` na raiz do projeto. Exemplo mínimo:
   ```env
   DEBUG=True
   SECRET_KEY=troque-esta-chave
   ALLOWED_HOSTS=localhost,127.0.0.1
   CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

   # Banco de dados (use um, senão cai no SQLite padrão)
   # DATABASE_URL=postgres://usuario:senha@host:5432/nome_db
   # ou RAILWAY_DATABASE_URL / POSTGRES_URL / POSTGRES_* variáveis

   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=seu-email@gmail.com
   EMAIL_HOST_PASSWORD=sua-senha-ou-app-password
   DEFAULT_FROM_EMAIL=seu-email@gmail.com
   CONTACT_EMAIL=destino-dos-contatos@gmail.com
   WHATSAPP_NUMBER=5599999999999
   ```
4. **Aplicar migrações**
   ```bash
   python manage.py migrate
   ```
5. **Criar um superusuário para acessar o admin**
   ```bash
   python manage.py createsuperuser
   ```
6. **(Opcional) Criar clientes**  
   Acesse `http://localhost:8000/admin/`, crie um Cliente e defina e-mail/senha. O admin sincroniza esses dados com o usuário padrão do Django.
7. **Executar o servidor de desenvolvimento**
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
   - Frontend principal: `http://localhost:8000/`
   - Login do cliente: `http://localhost:8000/login/`
   - Painel de processamento: `http://localhost:8000/processamento/`
   - Admin: `http://localhost:8000/admin/`

## Banco de dados
- **Desenvolvimento:** SQLite em `db.sqlite3` é usado automaticamente se nenhuma variável de banco for configurada.
- **Produção/PostgreSQL:** defina `DATABASE_URL` (ou `RAILWAY_DATABASE_URL`, `POSTGRES_URL`, ou o conjunto `POSTGRES_*`). SSL é respeitado se `sslmode` estiver na query string.

## Arquivos estáticos
- Assets estão em `app/core/static/`. Em produção, gere os arquivos coletados:
  ```bash
  python manage.py collectstatic --noinput
  ```
- WhiteNoise já está configurado em `settings.py` para servir estáticos.

## Envio de e-mails
O formulário de contato usa as credenciais definidas nas variáveis `EMAIL_*`. Configure `CONTACT_EMAIL` para o destinatário que receberá as mensagens; caso não defina, `EMAIL_HOST_USER` será usado.

## Execução em produção
- O `Procfile` já declara o comando:
  ```bash
  web: gunicorn LEITOR_FATURA.wsgi --log-file -
  ```
- Passos típicos:
  1. Definir variáveis de ambiente (incluindo `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` e `EMAIL_*`).
  2. Instalar dependências (`pip install -r requirements.txt`).
  3. Executar migrações (`python manage.py migrate`).
  4. Coletar estáticos (`python manage.py collectstatic --noinput`).
  5. Iniciar o servidor (`gunicorn LEITOR_FATURA.wsgi --bind 0.0.0.0:$PORT`).

## Testes
Ainda não há suíte de testes automatizados. Adicione testes em `app/core/tests.py` e `app/dashboard/tests.py` conforme novas funcionalidades forem implementadas.
