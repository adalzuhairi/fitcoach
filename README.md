# FitCoach — Plateforme de coaching sportif intelligent

Application web de musculation qui agit comme un coach sportif expérimenté :
génération de programmes d'entraînement personnalisés, plans nutritionnels et
suivi de progression. Les calculs métier (TDEE, macros, progression de charge)
sont codés en dur ; l'IA (API Claude) sert à générer les programmes et les
recettes.

Projet portfolio développé par Ahmed, étudiant en informatique de gestion
(Belgique). Interface en **français**, pensée mobile-first (l'app est surtout
utilisée à la salle, sur téléphone).

---

## Fonctionnalités

- **Onboarding guidé** — formulaire multi-étapes (profil, objectif, matériel,
  préférences), explications par champ, étape de récap, et visite guidée au
  premier passage (persistée côté serveur, multi-appareil).
- **Dashboard** — prochaine séance, calories/macros du jour, poids actuel,
  checklist de démarrage.
- **Mon programme** — split complet, détail de chaque journée
  (exercices, séries, reps, repos).
- **Mode séance** (mobile) — saisie rapide reps + charge, chrono de repos,
  suggestion de charge basée sur la dernière séance.
- **Nutrition** — calories et macros cibles, répartition par repas,
  recettes générées par IA.
- **Progression** — graphiques Chart.js (poids, charges, volume).
- **Mesures corporelles** — saisie + historique.
- **Bibliothèque d'exercices** — recherche/filtres, fiches techniques.
- **Multi-utilisateurs** — inscription / connexion / reset password
  (django-allauth).

---

## Stack technique

| Domaine | Technologie |
|---|---|
| Backend | Django 5+ (Python 3.12+) |
| Base de données | PostgreSQL 16 |
| Frontend | Templates Django + Tailwind CSS + Alpine.js |
| Graphiques | Chart.js |
| Cache / sessions | Redis |
| IA | API Anthropic (Claude) |
| Statiques en prod | WhiteNoise (manifest compressé) |
| Serveur d'app | Gunicorn |
| Conteneurisation | Docker + docker-compose |

---

## Architecture des apps

```
fitcoach/
├── config/       # settings, urls, wsgi
├── accounts/     # User personnalisé, profil, onboarding, visite guidée
├── nutrition/    # calculs TDEE/macros, repas, recettes
├── training/     # programmes, exercices, séances
├── tracking/     # logs de séances, mesures, dashboard, progression
└── coach/        # intégration API Claude (service layer)
```

Convention : la logique métier vit dans un `services.py` par app, jamais dans
les vues. Le code/commentaires métier sont en français.

---

## Démarrage en développement (Docker)

```bash
# 1. Cloner et configurer l'environnement
git clone <repo> fitcoach && cd fitcoach
cp .env.example .env            # ajuster si besoin (clé Anthropic, etc.)

# 2. Lancer la stack (web + db + redis)
#    docker-compose.override.yml est mergé automatiquement : ports publiés,
#    code monté en volume, runserver avec auto-reload.
docker compose up --build

# 3. Dans un autre terminal : migrations, fixtures, superuser
docker compose exec web python manage.py migrate
docker compose exec web python manage.py loaddata exercises
docker compose exec web python manage.py createsuperuser
```

L'application est accessible sur **http://localhost:8000**.

### Sans Docker (optionnel)

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py loaddata exercises
python manage.py runserver
```

Par défaut (hors Docker, sans `DJANGO_USE_POSTGRES`), Django utilise SQLite —
pratique pour un test rapide.

---

## Tests

La suite couvre notamment les formules de calcul (TDEE, macros, progression),
obligatoires.

```bash
docker compose exec web python manage.py test
# ou en local :
python manage.py test
```

---

## Variables d'environnement

Voir `.env.example` (dev) et `.env.prod.example` (prod) pour la liste complète
et commentée. Les clés principales :

| Variable | Rôle |
|---|---|
| `DJANGO_SECRET_KEY` | Clé secrète Django (forte en prod) |
| `DJANGO_DEBUG` | `True` en dev, `False` en prod |
| `DJANGO_ALLOWED_HOSTS` | Hôtes autorisés (CSV) |
| `DJANGO_SITE_DOMAIN` | Domaine du framework sites (URL absolues allauth) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origines de confiance CSRF (avec le port public) |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Base de données |
| `DJANGO_USE_REDIS` | Active Redis (cache + sessions) |
| `ANTHROPIC_API_KEY` | Clé API Claude (sinon recettes/programmes en fallback) |
| `ANTHROPIC_MODEL` | Modèle Claude (défaut `claude-sonnet-4-6`) |

> ⚠️ `.env` et `.env.prod` sont dans `.gitignore` — ne jamais les committer.
> Seuls les `*.example` sont versionnés.

---

## Déploiement en production

La prod tourne derrière **Traefik** (reverse proxy, terminaison TLS via DNS
challenge Infomaniak) sur le domaine `fitcoach.infotechno.eu`.

```bash
# Sur la VM (Traefik déjà en place avec son réseau "frontend")
git pull
cp .env.prod.example .env.prod          # remplir les vraies valeurs
#   → DJANGO_SITE_DOMAIN=fitcoach.infotechno.eu:4443 dès le premier build
#     (la migration qui fixe le Site ne s'exécute qu'une fois)

docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file .env.prod up -d --build

# Suivre le démarrage : attente DB → migrate → collectstatic → gunicorn
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file .env.prod logs -f web

# Superuser
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file .env.prod exec web python manage.py createsuperuser
```

L'`entrypoint.sh` se charge automatiquement de l'attente de la base, des
migrations et du `collectstatic` au démarrage du conteneur.

**Pré-requis côté infra** : enregistrement DNS pointant vers la VM, réseau
Docker externe `frontend`, certresolver `infomaniak` et entrypoint `websecure`
configurés dans le Traefik existant.

---

## Conventions

- Code/commentaires métier en **français**, code technique en anglais accepté.
- Un `services.py` par app pour la logique métier.
- `makemigrations` après chaque modif de modèle, migrations propres.
- Tests unitaires obligatoires sur les formules de calcul.
