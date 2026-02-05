set -e

echo "Waiting for PostgreSQL..."
while ! pg_isready -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
  sleep 2
done

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Starting server..."
exec python manage.py runserver 0.0.0.0:8000