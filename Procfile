release: python vaccinate/manage.py migrate --noinput
web: sh -c 'cd vaccinate && gunicorn config.wsgi'
