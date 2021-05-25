FROM python:3.9-slim

ENV APP_HOME /app
WORKDIR $APP_HOME

ENV PYTHONUNBUFFERED 1

# gdal for GeoDjango
RUN apt-get update && apt-get install -y \
    binutils \
    gdal-bin \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vaccinate/ vaccinate/
COPY docs/ docs/

# Passed down by Cloud Build, which we make available at runtime
ARG COMMIT_SHA
ENV COMMIT_SHA=${COMMIT_SHA}

# Pulled in at runtime
ENV DEPLOY=unknown

WORKDIR $APP_HOME/vaccinate

# Running manage.py requires a full set of environment variables,
# despite `collectstatic` not caring what they are.
RUN DJANGO_SECRET_KEY=1 SOCIAL_AUTH_AUTH0_SECRET= ./manage.py collectstatic --no-input

CMD exec gunicorn -c config/gunicorn.py --workers 1 --threads 8 --timeout 0 --preload -b :$PORT config.wsgi

