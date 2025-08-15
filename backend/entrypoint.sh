#!/usr/bin/env bash
set -e

# Wait for Postgres to be ready
echo "Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
until pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" >/dev/null 2>&1; do
  sleep 1
done
echo "Postgres is ready."

# Run migrations and start server
python manage.py migrate --noinput

# Collect static (noop early on)
python manage.py collectstatic --noinput || true

# Start dev server
exec python manage.py runserver 0.0.0.0:8000
