FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances système pour psycopg / build
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# entrypoint de prod (attente DB → migrate → collectstatic → gunicorn).
# Utilisé par docker-compose.prod.yml ; ignoré en dev (commande surchargée).
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# Le serveur de dev est lancé via docker-compose (commande surchargée).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
