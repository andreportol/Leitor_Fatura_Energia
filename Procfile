release: python3 manage.py migrate --noinput && python3 manage.py collectstatic --noinput
web: gunicorn --timeout 120 --log-file - LEITOR_FATURA.wsgi
