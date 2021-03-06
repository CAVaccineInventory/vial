FROM python:3.9-slim

ENV APP_HOME /app
WORKDIR $APP_HOME

ENV PYTHONUNBUFFERED 1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vaccinate/ vaccinate/


# Pulled in at runtime
ENV DEPLOY=unknown

WORKDIR $APP_HOME/vaccinate

# Running manage.py requires a full set of environment variables,
# despite `collectstatic` not caring what they are.
RUN DJANGO_SECRET_KEY=1 SOCIAL_AUTH_AUTH0_SECRET= ./manage.py collectstatic --no-input

CMD exec gunicorn -b :$PORT config.wsgi

