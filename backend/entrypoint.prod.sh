#!/bin/sh
set -eu

if [ "${DJANGO_RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${DJANGO_COLLECTSTATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec gunicorn config.wsgi:application -c /app/gunicorn.conf.py
