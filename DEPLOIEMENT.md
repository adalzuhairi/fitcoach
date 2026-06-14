# Déploiement de FitCoach

Guide de mise en production de FitCoach sur une **VM auto-hébergée**, branché sur
le reverse proxy **Traefik** déjà en place (comme dockhand, it-tools, tinyauth),
avec le domaine **fitcoach.infotechno.eu**.

Le HTTPS public passe par l'entrypoint Traefik **:4443** (les ports standards
sont déjà occupés sur la VM). Tu accéderas donc à l'app sur
**https://fitcoach.infotechno.eu:4443**.

Architecture cible :

```
Internet
   │  (DNS A/CNAME : fitcoach.infotechno.eu → même cible que tes autres sous-domaines)
   ▼
VM
   │
   ▼
Traefik (reverse proxy + TLS, déjà installé)
   │   entrypoint websecure :4443
   │   certificat Let's Encrypt via DNS challenge Infomaniak
   │   (routage par labels Docker + réseau "frontend")
   ▼
docker compose (web Gunicorn :8000 + db + redis)
```

---

## 1. Pré-requis sur la VM

- Docker + plugin Docker Compose (`docker compose version`)
- **Traefik déjà en service** avec :
  - un réseau Docker externe partagé (supposé `frontend` — **à vérifier**)
  - un certresolver DNS Infomaniak (supposé `infomaniak` — **à vérifier**)
  - l'entrypoint `websecure` sur :4443
- Le dépôt cloné (ou l'image transférée) sur la VM

> Vérifier les deux noms ci-dessus sur le `docker-compose.yml` de dockhand ou
> it-tools : ils doivent correspondre **exactement** aux labels de FitCoach,
> sinon Traefik ne routera pas. Voir §4.

---

## 2. Configuration des variables d'environnement

```bash
cp .env.prod.example .env.prod
```

Éditez `.env.prod` et renseignez **au minimum** :

| Variable | Rôle |
|----------|------|
| `DJANGO_SECRET_KEY` | Clé secrète unique (voir commande ci-dessous) |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL fort |
| `ANTHROPIC_API_KEY` | Clé API Claude |

Générer une `SECRET_KEY` :

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

> `.env.prod` est ignoré par git. Ne le committez jamais.
> `DJANGO_ALLOWED_HOSTS` et `DJANGO_CSRF_TRUSTED_ORIGINS` sont déjà calés sur
> `fitcoach.infotechno.eu` dans le modèle.

---

## 3. Build et lancement des conteneurs

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Au démarrage, `entrypoint.sh` (dans le conteneur `web`) effectue automatiquement :

1. attente que PostgreSQL soit prêt ;
2. `python manage.py migrate` ;
3. `python manage.py collectstatic` (servi ensuite par WhiteNoise) ;
4. démarrage de Gunicorn sur le port 8000 (exposé sur `127.0.0.1:8000`).

Vérifier l'état :

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f web
```

### Créer un superutilisateur

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### Charger la fixture d'exercices (premier déploiement)

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py loaddata exercises
```

---

## 4. Reverse proxy Traefik (déjà en place sur la VM)

Pas de nginx ni de Certbot : FitCoach se branche sur ton Traefik existant via des
**labels Docker**, exactement comme dockhand/it-tools. Tout est déjà déclaré dans
`docker-compose.prod.yml` (service `web`) :

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.docker.network=frontend"
  - "traefik.http.routers.fitcoach.rule=Host(`fitcoach.infotechno.eu`)"
  - "traefik.http.routers.fitcoach.entrypoints=websecure"
  - "traefik.http.routers.fitcoach.tls=true"
  - "traefik.http.routers.fitcoach.tls.certresolver=infomaniak"
  - "traefik.http.services.fitcoach.loadbalancer.server.port=8000"
```

Et le service est rattaché au réseau externe partagé avec Traefik :

```yaml
networks:
  frontend:
    external: true
```

### ⚠️ Deux noms à faire correspondre à ta config Traefik

Avant de lancer, ouvre le `docker-compose.yml` de **dockhand** ou **it-tools** sur
la VM et confirme :

| Élément | Valeur supposée | Où la corriger si différente |
|---------|-----------------|------------------------------|
| Réseau Docker externe de Traefik | `frontend` | label `traefik.docker.network` **et** bloc `networks:` |
| Nom du certresolver Infomaniak | `infomaniak` | label `...tls.certresolver` |

Si ces noms ne matchent pas **exactement**, Traefik ne créera pas le routeur et
le certificat ne sera pas émis.

### Vérifier le routage

Après `up -d`, contrôle dans le **dashboard Traefik** (`:9090`) que le routeur
`fitcoach` apparaît bien en HTTPS sur l'entrypoint `websecure`, sans erreur de
certificat. Le certificat Let's Encrypt est obtenu automatiquement par Traefik
via le **DNS challenge Infomaniak** — aucune ouverture de port 80 nécessaire.

---

## 5. Côté réseau (à faire manuellement)

Grâce à Traefik, c'est beaucoup plus léger que pour une stack nginx/Certbot :

1. **DNS chez Infomaniak** : ajoute un enregistrement **A ou CNAME**
   `fitcoach.infotechno.eu` pointant vers **la même cible que tes autres
   sous-domaines** (`dockhand`, `it-tools`…). Le plus simple : copie la
   configuration de `dockhand`.
   - Comme le certificat est émis par **DNS challenge** (et non HTTP-01), tu n'as
     **pas** besoin d'exposer le port 80, ni de gérer l'IP dynamique pour la
     validation TLS.
2. **Accès** : aucune redirection de port supplémentaire à créer si Traefik est
   déjà joignable de l'extérieur sur **:4443** (cas de tes autres services).
   L'app sera disponible sur **https://fitcoach.infotechno.eu:4443**.
3. **Réseau Docker** : le réseau externe `frontend` doit exister (il est déjà
   créé par la stack Traefik). En cas de doute : `docker network ls`.

---

## 6. Mises à jour ultérieures

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Les migrations et `collectstatic` sont rejoués automatiquement par l'entrypoint.

### Sauvegarde de la base

```bash
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U fitcoach fitcoach > backup_$(date +%F).sql
```

Les données persistent dans les volumes Docker `postgres_data`, `redis_data` et
`media_data` (conservés entre les redéploiements).

---

## 7. Dépannage rapide

| Symptôme | Piste |
|----------|-------|
| `400 Bad Request` | Domaine absent de `DJANGO_ALLOWED_HOSTS` |
| Échec POST / formulaires | `DJANGO_CSRF_TRUSTED_ORIGINS` mal configuré |
| Boucle de redirection HTTPS | nginx ne transmet pas `X-Forwarded-Proto` |
| CSS/JS absents | `collectstatic` échoué — voir `logs web` |
| `web` redémarre en boucle | DB indisponible / `.env.prod` incomplet |
```
