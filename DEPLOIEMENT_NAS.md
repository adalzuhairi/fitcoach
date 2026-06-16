# Déploiement de FitCoach sur NAS Synology DS713+

Guide pas-à-pas pour héberger FitCoach sur un **Synology DS713+** (CPU Intel
Atom Cedarview, x86_64, 2 cœurs, 4 Go de RAM), sous **DSM 6.2**, avec le paquet
**Docker** classique (pas de Container Manager) et le **reverse proxy intégré de
DSM** (pas de Traefik).

La stack reste identique à la prod VM : **Django + PostgreSQL + Redis**. Seule
l'enveloppe de déploiement change (`docker-compose.nas.yml`, `.env.nas`).

> ⚠️ **Contrainte matérielle.** Le DS713+ date de 2013 (Atom bi-cœur). L'app
> fonctionne, mais sera **plus lente** que sur la VM — en particulier la
> **génération IA** des programmes/recettes (appel à l'API Claude). C'est pour
> ça que gunicorn tourne en **2 workers** (2 cœurs) avec un **timeout de 120 s**.

---

## 0. Pré-requis — version Docker du NAS

Vérifié sur ce DS713+ : **Docker 20.10.3** avec **Docker Compose v1 uniquement**
(`docker-compose` 1.28.5, avec **tiret**). Il n'y a **pas** de `docker compose`
v2 (avec espace).

Conséquences appliquées dans ce guide :
- Toutes les commandes utilisent **`docker-compose`** (avec tiret).
- Le schéma `version: "3.7"` de `docker-compose.nas.yml` est supporté par
  1.28.5 — rien à abaisser.

```bash
# Pour mémoire, les commandes de vérification (SSH sur le NAS) :
sudo docker --version            # Docker version 20.10.3
sudo docker-compose --version    # docker-compose version 1.28.5
```

> Sur Synology, Docker requiert souvent `sudo`. Les commandes de ce guide
> l'omettent pour la lisibilité ; ajoute `sudo` devant si nécessaire.

---

## 1. Build de l'image sur la VM (pas sur le NAS)

On **ne construit pas** sur l'Atom (lent, pas de toolchain). On build sur la VM
(ou ta machine de dev Linux/x86_64), puis on exporte l'image.

```bash
# Sur la VM, à la racine du dépôt (branche nas)
git pull
docker build -t fitcoach-web:latest .

# Export de l'image dans un fichier tar
docker save fitcoach-web:latest -o fitcoach.tar
```

> L'image doit être construite pour **x86_64** (cas par défaut sur la VM) —
> compatible avec l'Atom du DS713+.

---

## 2. Transfert du tar sur le NAS

Au choix :

```bash
# Via scp (remplace l'utilisateur, l'hôte et le chemin)
scp fitcoach.tar admin@NAS_IP:/volume1/docker/fitcoach/
```

…ou par **File Station** (interface DSM) : dépose `fitcoach.tar` dans
`/volume1/docker/fitcoach/`.

Transfère aussi sur le NAS, dans le même dossier projet, les fichiers de
déploiement de la branche `nas` :
- `docker-compose.nas.yml`
- `.env.nas.example` (que tu copieras en `.env.nas`)

> Le plus simple : faire un `git clone`/`git pull` du dépôt directement sur le
> NAS pour récupérer `docker-compose.nas.yml` et `.env.nas.example`, et n'y
> transférer que `fitcoach.tar`.

---

## 3. Import de l'image sur le NAS

```bash
# En SSH sur le NAS
docker load -i /volume1/docker/fitcoach/fitcoach.tar
docker images | grep fitcoach-web        # vérifie que fitcoach-web:latest est présent
```

---

## 4. Création des dossiers de volumes (bind mounts DSM)

Les données vivent sous `/volume1/docker/fitcoach/` pour être **visibles et
sauvegardables depuis DSM** (Hyper Backup, etc.).

```bash
mkdir -p /volume1/docker/fitcoach/postgres
mkdir -p /volume1/docker/fitcoach/media
mkdir -p /volume1/docker/fitcoach/redis
```

> Le dossier `postgres/` doit être **vide** au premier démarrage : l'image
> PostgreSQL l'initialise toute seule. Si tu rencontres une erreur de
> permission au démarrage de `db`, c'est lié aux droits du bind mount — voir la
> section *Dépannage*.

---

## 5. Configuration de l'environnement

```bash
cd /volume1/docker/fitcoach          # dossier contenant docker-compose.nas.yml
cp .env.nas.example .env.nas
vi .env.nas                          # (ou éditer via File Station / éditeur DSM)
```

À renseigner dans `.env.nas` :
- `DJANGO_SECRET_KEY` — une vraie clé forte.
- `POSTGRES_PASSWORD` — un mot de passe fort.
- `ANTHROPIC_API_KEY` — ta clé Claude (sinon génération IA en mode fallback).
- L'hôte est déjà calé sur **`nasinfotechno.synology.me`** via le DDNS Synology,
  port **`:8443`**. ⚠️ `SITE_DOMAIN` et `CSRF_TRUSTED_ORIGINS` incluent le port
  (`nasinfotechno.synology.me:8443`) — ne le retire pas, sinon CSRF cassé.
- `NAS_DATA=/volume1/docker/fitcoach` (chemin des bind mounts).

---

## 6. Lancement de la stack

```bash
docker-compose -f docker-compose.nas.yml --env-file .env.nas up -d
```

L'`entrypoint.sh` du conteneur `web` s'occupe automatiquement de :
attente de PostgreSQL → `migrate` → `collectstatic` → démarrage de gunicorn.

Suis le démarrage :

```bash
docker-compose -f docker-compose.nas.yml --env-file .env.nas logs -f web
```

Tu dois voir : *⏳ Attente de PostgreSQL… ✅ … 🛠 migrations … 🎨 collectstatic …
🚀 Démarrage : gunicorn*.

---

## 7. Initialisation (migrations, données, superuser)

Les **migrations** sont déjà appliquées par l'entrypoint au démarrage. Reste à
charger les exercices et créer le compte admin :

```bash
# Fixture des ~60 exercices de base
docker-compose -f docker-compose.nas.yml --env-file .env.nas \
  exec web python manage.py loaddata exercises

# Superuser — saisie INTERACTIVE du mot de passe (jamais en clair sur la ligne)
docker-compose -f docker-compose.nas.yml --env-file .env.nas \
  exec web python manage.py createsuperuser
```

> La migration `0003_site_domain` règle le domaine allauth depuis
> `DJANGO_SITE_DOMAIN` **au premier `migrate`**. Assure-toi que `.env.nas`
> contient bien `nasinfotechno.synology.me:8443` **avant** le premier `up`.
> (Sinon, corrige ensuite le Site dans l'admin Django.)

---

## 8. Reverse proxy DSM + certificat HTTPS

Dans **DSM → Panneau de configuration → Portail des applications → Proxy
inversé** (selon DSM : *Réseau → Reverse Proxy*), crée une règle :

| Champ | Valeur |
|---|---|
| **Source — Protocole** | HTTPS |
| **Source — Nom d'hôte** | `nasinfotechno.synology.me` |
| **Source — Port** | `8443` |
| **Destination — Protocole** | HTTP |
| **Destination — Nom d'hôte** | `localhost` |
| **Destination — Port** | `8001` |

> Le port **8443** doit être **ouvert/forwardé sur ta box** vers le NAS (c'est le
> port public de FitCoach, distinct du `65001` de DSM).

Dans l'onglet **En-têtes personnalisés**, ajoute (bouton *Créer → WebSocket*
pour les deux premiers, puis manuellement) :

```
X-Forwarded-Proto   $scheme
X-Forwarded-For     $proxy_add_x_forwarded_for
X-Real-IP           $remote_addr
Host                $host
```

> `X-Forwarded-Proto` est **indispensable** : c'est lui qui indique à Django que
> la requête d'origine est en HTTPS (`SECURE_PROXY_SSL_HEADER`). Sans lui, tu
> auras une boucle de redirection (`SECURE_SSL_REDIRECT`).

### Certificat Let's Encrypt via DSM

Le DDNS Synology te donne un certificat natif **sans ligne de commande** :

**Panneau de configuration → Sécurité → Certificat → Ajouter → Obtenir un
certificat de Let's Encrypt** :
- Nom de domaine : `nasinfotechno.synology.me`
- E-mail valide
- Puis **Configurer** le certificat pour qu'il serve le service *Proxy inversé*
  `nasinfotechno.synology.me:8443`.

> Comme le domaine `synology.me` est géré par Synology, la validation Let's
> Encrypt fonctionne nativement — pas besoin de toucher à un DNS externe.

Ouvre ensuite **https://nasinfotechno.synology.me:8443** 🎉

---

## Dépannage

- **Boucle de redirection / ERR_TOO_MANY_REDIRECTS** → l'en-tête
  `X-Forwarded-Proto` n'arrive pas à Django. Vérifie les en-têtes du proxy DSM,
  ou en dernier recours passe `DJANGO_SECURE_SSL_REDIRECT=False` dans `.env.nas`.
- **`db` ne démarre pas (permission denied sur le volume)** → le bind mount
  `postgres/` a de mauvais droits. Vérifie qu'il est vide, ou ajuste les droits
  (`chown -R 999:999 /volume1/docker/fitcoach/postgres` — 999 = uid postgres de
  l'image).
- **502 / page lente à la génération du programme** → normal sur l'Atom au
  premier appel IA ; le timeout gunicorn est déjà à 120 s. Patiente.
- **Statiques absents (CSS cassé)** → `collectstatic` est lancé par
  l'entrypoint ; en cas de doute, relance-le :
  `... exec web python manage.py collectstatic --noinput`.
- **Erreur CSRF sur les formulaires** → vérifie que
  `https://nasinfotechno.synology.me:8443` figure bien dans
  `DJANGO_CSRF_TRUSTED_ORIGINS` — **avec `https://` ET le port `:8443`**.

---

## Mise à jour de l'app (déploiements suivants)

```bash
# Sur la VM : rebuild + export
git pull && docker build -t fitcoach-web:latest . && docker save fitcoach-web:latest -o fitcoach.tar
# Transfert du tar sur le NAS, puis sur le NAS :
docker load -i fitcoach.tar
docker-compose -f docker-compose.nas.yml --env-file .env.nas up -d
# (l'entrypoint réapplique migrations + collectstatic au redémarrage)
```
