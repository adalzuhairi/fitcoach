# FitCoach — Plateforme de coaching sportif intelligent

## Contexte du projet

Application web de musculation qui agit comme un coach sportif expérimenté : génération de programmes d'entraînement personnalisés (exercices, séries, répétitions, temps de repos), plans nutritionnels (calories, macros, repas, recettes) et suivi de progression. Développé par Ahmed, étudiant en informatique de gestion (Belgique). Usage personnel d'abord, multi-utilisateurs ensuite (projet portfolio évolutif).

## Stack technique

- **Backend** : Django 5+ (Python 3.12+)
- **Base de données** : PostgreSQL 16
- **Frontend** : Templates Django + Tailwind CSS (via CDN en dev, build en prod) + Alpine.js pour l'interactivité légère
- **Graphiques** : Chart.js
- **Conteneurisation** : Docker + docker-compose (web + db + redis)
- **Cache/tâches** : Redis (sessions, cache des plans générés)
- **IA** : API Anthropic (modèle claude-sonnet) pour la génération de programmes et recettes
- **Langue de l'interface** : Français

## Design system

- Accent principal : bleu #2563EB
- Sidebar sombre (#0F172A), contenu clair
- Typographie : Inter
- Style moderne, épuré, cartes avec coins arrondis (rounded-xl), ombres légères
- Responsive mobile-first (l'app sera surtout utilisée à la salle sur téléphone)

## Architecture des apps Django

```
fitcoach/
├── config/          # settings, urls, wsgi
├── accounts/        # User personnalisé, profil, onboarding
├── nutrition/       # calculs TDEE/macros, repas, recettes
├── training/        # programmes, exercices, séances
├── tracking/        # logs de séances, mesures, graphiques
└── coach/           # intégration API Claude (service layer)
```

## Modèles de données

### accounts.Profile (OneToOne avec User)
- sexe (H/F), date_naissance, taille_cm, poids_kg
- niveau : débutant / intermédiaire / avancé
- objectif : prise_de_masse / seche / recomposition / force / maintien
- activite : sedentaire / leger / modere / actif / tres_actif
- jours_entrainement_par_semaine (2 à 6)
- materiel : salle_complete / halteres_maison / poids_du_corps
- blessures_limitations (TextField, optionnel)
- allergies_alimentaires (TextField, optionnel)
- preferences_alimentaires (ex: halal, végétarien, sans porc)

### training.Exercise
- nom, nom_en, groupe_musculaire (pectoraux, dos, jambes, épaules, biceps, triceps, abdos, mollets)
- type : compose / isolation
- materiel_requis, niveau_minimum
- description_technique (consignes d'exécution)
- video_url (optionnel)

### training.Program
- user (FK), nom, objectif, date_debut, duree_semaines (4/8/12)
- split : full_body / half_body / push_pull_legs / split_classique
- actif (booléen), genere_par_ia (booléen)
- prompt_ia / reponse_ia (JSONField, pour traçabilité)

### training.WorkoutDay
- program (FK), jour_numero, nom (ex: "Push — Pectoraux/Épaules/Triceps")

### training.WorkoutExercise
- workout_day (FK), exercise (FK), ordre
- series, repetitions (ex: "8-12"), temps_repos_secondes
- tempo (optionnel, ex: "2-0-2"), notes
- progression_type : double_progression / charge_lineaire / rpe

### nutrition.NutritionPlan
- user (FK), date_creation, actif
- tdee_calcule, calories_cibles, proteines_g, glucides_g, lipides_g
- nombre_repas (3 à 6)

### nutrition.Meal
- plan (FK), nom (petit-déj, déjeuner, collation, dîner), ordre
- calories, proteines_g, glucides_g, lipides_g

### nutrition.Recipe
- nom, description, instructions (TextField)
- temps_preparation_min, portions
- calories, proteines_g, glucides_g, lipides_g (par portion)
- ingredients (JSONField : liste {nom, quantite, unite})
- tags (prise_de_masse, seche, rapide, batch_cooking, halal, etc.)
- generee_par_ia (booléen)

### tracking.WorkoutLog
- user (FK), workout_day (FK), date, duree_minutes, ressenti (1-5), notes

### tracking.SetLog
- workout_log (FK), workout_exercise (FK)
- serie_numero, repetitions_faites, charge_kg, rpe (optionnel)

### tracking.BodyMeasurement
- user (FK), date, poids_kg
- tour_taille, tour_bras, tour_poitrine, tour_cuisses (cm, optionnels)
- photo (optionnel)

## Logique métier — Formules (codées en dur, PAS via IA)

### TDEE — Mifflin-St Jeor
- Homme : BMR = 10 × poids(kg) + 6,25 × taille(cm) − 5 × âge + 5
- Femme : BMR = 10 × poids(kg) + 6,25 × taille(cm) − 5 × âge − 161
- TDEE = BMR × facteur activité (1.2 / 1.375 / 1.55 / 1.725 / 1.9)

### Calories cibles selon objectif
- Prise de masse : TDEE + 250 à 350 kcal
- Sèche : TDEE − 400 à 500 kcal
- Recomposition / maintien : TDEE
- Force : TDEE + 100 à 200 kcal

### Macros
- Protéines : 1,8 à 2,2 g/kg de poids de corps (2,2 en sèche)
- Lipides : 0,8 à 1 g/kg (minimum 0,6)
- Glucides : le reste des calories
- 1 g protéine = 4 kcal, 1 g glucide = 4 kcal, 1 g lipide = 9 kcal

### Progression (double progression par défaut)
- Si toutes les séries atteignent le haut de la fourchette de reps → +2,5 kg (haut du corps) ou +5 kg (bas du corps) à la séance suivante
- Afficher automatiquement la suggestion de charge basée sur le dernier SetLog

### Temps de repos par défaut
- Exercices composés lourds (squat, soulevé de terre, développé) : 150-180 s
- Composés modérés : 90-120 s
- Isolation : 60-90 s

## Intégration API Claude (app `coach/`)

Créer un service `coach/services.py` avec :

### `generate_program(profile)`
- Construit un prompt structuré avec : objectif, niveau, jours/semaine, matériel, blessures
- Demande une réponse JSON strict : `{split, jours: [{nom, exercices: [{nom, series, reps, repos_s, notes}]}]}`
- Mappe les exercices retournés sur la table Exercise (matching par nom, créer si absent avec flag à valider)
- Sauvegarde le programme complet en une transaction

### `generate_recipes(profile, meal, n=3)`
- Génère des recettes respectant les macros cibles du repas, les allergies et préférences alimentaires
- Réponse JSON strict, sauvegarde en Recipe

### `adapt_program(program, feedback)`
- Si stagnation détectée (3 séances sans progression sur un exercice) ou feedback utilisateur, propose des ajustements

### Règles d'implémentation IA
- Clé API dans variable d'environnement `ANTHROPIC_API_KEY` (jamais en dur, utiliser python-dotenv)
- Utiliser le SDK officiel `anthropic` (pip)
- System prompt : "Tu es un coach sportif et nutritionniste expérimenté. Réponds UNIQUEMENT en JSON valide, sans markdown."
- try/except + retry (1 fois) + fallback sur des templates de programmes prédéfinis si l'API échoue
- Mettre en cache les réponses (Redis) pour éviter les appels redondants

## Pages / Fonctionnalités

### Phase 1 — MVP (priorité absolue)
1. **Onboarding** : formulaire multi-étapes (profil, objectif, matériel, préférences) → calcule TDEE/macros → génère le premier programme via IA
2. **Dashboard** : prochaine séance, calories/macros du jour, poids actuel, mini-graphique de progression
3. **Mon programme** : vue du split complet, détail de chaque journée avec exercices/séries/reps/repos
4. **Mode séance** (page clé, optimisée mobile) : exercice en cours, saisie rapide reps + charge par série, chrono de repos automatique avec son/vibration, suggestion de charge basée sur la dernière séance, bouton "série terminée"
5. **Ma nutrition** : calories et macros cibles, répartition par repas, recettes suggérées

### Phase 2
6. **Progression** : graphiques Chart.js (poids corporel, charges par exercice, volume hebdomadaire)
7. **Bibliothèque d'exercices** : recherche/filtres par groupe musculaire, fiches techniques
8. **Recettes IA** : génération à la demande selon le repas et les macros restantes
9. **Mesures corporelles** : saisie + historique + graphiques

### Phase 3 — Multi-utilisateurs
10. Inscription/connexion (django-allauth), reset password
11. Landing page publique (présentation du produit)
12. Espace admin pour valider les exercices créés par l'IA

## Données initiales (fixtures)

Créer une fixture `exercises.json` avec ~60 exercices de base couvrant tous les groupes musculaires (développé couché, squat, soulevé de terre, tractions, rowing, développé militaire, curl, extensions triceps, etc.) avec descriptions techniques en français.

## Conventions de code

- Code et commentaires en français pour les modèles métier, anglais accepté pour le code technique
- Class-Based Views Django quand pertinent, sinon function views simples
- Un fichier `services.py` par app pour la logique métier (pas de logique dans les views)
- Tests unitaires sur les formules de calcul (TDEE, macros, progression) — obligatoire
- Migrations propres, `python manage.py makemigrations` après chaque modif de modèle
- `.env.example` fourni, `.env` dans .gitignore

## Ordre de développement recommandé

1. Setup projet : Django + Docker + PostgreSQL + structure des apps
2. Modèles + migrations + fixture exercices + admin Django
3. Formules nutrition (services + tests)
4. Onboarding + Profile
5. Service coach IA (génération programme) avec fallback templates
6. Pages programme + mode séance
7. Page nutrition
8. Dashboard
9. Phase 2 puis 3
