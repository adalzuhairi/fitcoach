#!/bin/sh
# Entrypoint de production FitCoach.
# Attend que PostgreSQL soit prêt, applique les migrations, collecte les
# fichiers statiques, puis lance la commande passée en argument (gunicorn).
set -e

# --- Attente de la base de données ---------------------------------------
# On boucle tant que la connexion TCP au PostgreSQL n'est pas établie.
DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "⏳ Attente de PostgreSQL sur ${DB_HOST}:${DB_PORT}..."
until python -c "import socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(0) if s.connect_ex(('${DB_HOST}', ${DB_PORT}))==0 else sys.exit(1)" 2>/dev/null; do
  echo "   ...base indisponible, nouvelle tentative dans 2s"
  sleep 2
done
echo "✅ PostgreSQL est prêt."

# --- Migrations ----------------------------------------------------------
echo "🛠  Application des migrations..."
python manage.py migrate --noinput

# --- Fichiers statiques --------------------------------------------------
echo "🎨 Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

# --- Démarrage du serveur d'application ----------------------------------
echo "🚀 Démarrage : $*"
exec "$@"
