
# 🎬 CineQuote AI 2.0

### Testez vos connaissances cinématographiques grâce à l'intelligence artificielle !

**CineQuote AI** est une application web full-stack de quiz cinématographique intégrant l'intelligence artificielle.

Le principe est simple : une citation de film apparaît à l'écran et le joueur doit retrouver le film correspondant parmi quatre propositions.

Le projet combine développement web, API REST, gestion de bases de données, authentification sécurisée et intégration de modèles d'intelligence artificielle.

### 🌐 [🎮 Jouer à CineQuote AI](https://cine-quote-ai.vercel.app)

**Projet développé dans le cadre de mon portfolio en développement logiciel et intelligence artificielle.**

---

## 📸 Aperçu de l'application



![Page d'accueil de CineQuote AI](docs/screenshots/accueil.png)



![Sélection du quiz](docs/screenshots/selection-quiz.png)



![Question de quiz](docs/screenshots/question.png)




![Résultats du quiz](docs/screenshots/resultats.png)

![iaChoice](docs/screenshots/iaChoice.png)

> **Remarque :** les images ci-dessus doivent être ajoutées dans le dossier `docs/screenshots/` du dépôt GitHub pour être affichées.

---

## ✨ Fonctionnalités

### 🎮 Quiz cinématographique

- Sessions de 10 questions.
- Quatre films proposés pour chaque citation.
- Trois niveaux de difficulté : **Easy, Medium et Hard**.
- Sélection de différents genres cinématographiques.
- Mode regroupant tous les genres.
- Questions et réponses mélangées aléatoirement.
- Filtrage des questions selon les genres sélectionnés.
- Quiz personnalisés à partir d'une demande en langage naturel.

### 🎭 Genres disponibles

- Horreur
- Comédie
- Science-fiction
- Thriller
- Action
- Animation
- Romance / Comédie musicale
- Fantasy
- Aventure

### 🤖 Intelligence artificielle

CineQuote AI utilise **GroqCloud** pour intégrer des fonctionnalités d'intelligence artificielle au jeu.

Les principales fonctionnalités comprennent :

- Génération d'indices contextuels.
- Explications après les réponses.
- Conseils personnalisés selon les performances.
- Recommandations de films à découvrir.
- Création de quiz personnalisés à partir d'instructions textuelles.

L'application prend également en charge OpenAI comme fournisseur alternatif.

Des mécanismes de validation, de limitation des requêtes et de repli permettent de maintenir le fonctionnement du jeu lorsque les services d'IA sont indisponibles.

**L'intelligence artificielle n'est pas responsable de la sélection des bonnes réponses ni du calcul des scores.** Ces opérations sont contrôlées par le backend afin de garantir la cohérence du quiz.

### 👤 Comptes et statistiques

- Possibilité de jouer sans compte.
- Inscription et connexion sécurisées.
- Suivi des performances pour les utilisateurs connectés.
- Conservation des statistiques dans une base de données.
- Sessions d'authentification utilisant des cookies HTTP-only.

---

## 🛠️ Technologies utilisées

| Domaine | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite, CSS |
| Backend | Python, FastAPI, Pydantic |
| Base de données | PostgreSQL, SQLite |
| ORM et migrations | SQLAlchemy, Alembic |
| Intelligence artificielle | GroqCloud, OpenAI |
| Tests | pytest, Vitest, FastAPI TestClient |
| Hébergement frontend | Vercel |
| Hébergement backend | Render |
| Base de données cloud | Neon |
| Versionnement | Git, GitHub |

---

## 🏗️ Architecture du projet

CineQuote AI repose sur une architecture full-stack séparant le frontend, le backend et la base de données.

```text
                  UTILISATEUR
                       |
                       v
             +-------------------+
             |      VERCEL       |
             |  React / Vite     |
             |  TypeScript       |
             +-------------------+
                       |
                       | Requêtes /api
                       v
             +-------------------+
             |   PROXY VERCEL    |
             +-------------------+
                       |
                       v
             +-------------------+
             |      RENDER       |
             |  Python / FastAPI |
             +-------------------+
                  |         |
                  v         v
          +-----------+  +-------------+
          |   NEON    |  |  GROQCLOUD  |
          | PostgreSQL|  |     IA      |
          +-----------+  +-------------+
```

### Frontend

Le frontend est développé avec **React, TypeScript et Vite**.

Il gère notamment :

- L'interface utilisateur.
- La navigation entre les différents écrans.
- La sélection des quiz.
- L'affichage des questions et des réponses.
- Les interactions avec l'API.
- L'affichage des résultats et des statistiques.

### Backend

Le backend est développé en **Python avec FastAPI**.

Il prend en charge :

- La gestion du catalogue de films et de citations.
- La création des sessions de quiz.
- La sélection des questions.
- La vérification des réponses.
- Le calcul des scores.
- L'authentification.
- Les statistiques.
- Les communications avec les fournisseurs d'intelligence artificielle.

Les bonnes réponses ne sont pas transmises au navigateur avant la validation des questions.

### Base de données

L'application utilise :

- **SQLite** pour le développement local.
- **PostgreSQL sur Neon** pour la production.

Les migrations sont gérées avec Alembic.

---

## 🎞️ Catalogue cinématographique

Le catalogue contient actuellement :

- **73 films**
- **421 citations**
- Plusieurs genres cinématographiques
- Différents niveaux de difficulté

Les citations sont sélectionnées et vérifiées manuellement.

Le catalogue est stocké dans :

`back/app/data/manual_catalog.json`

Un film peut posséder plusieurs citations et appartenir à plusieurs genres.

---

## 📁 Structure du projet

```text
CineQuote-AI/
|
|-- back/
|   |-- alembic/              # Migrations SQL
|   |-- app/
|   |   |-- api/routes/       # Routes FastAPI
|   |   |-- catalog/          # Gestion du catalogue
|   |   |-- data/             # Films et citations
|   |   |-- middleware/       # Sécurité
|   |   |-- models/           # Modèles SQLAlchemy
|   |   |-- repositories/     # Accès aux données
|   |   |-- schemas/          # Schémas Pydantic
|   |   `-- services/         # Quiz, comptes, IA
|   |-- scripts/              # Scripts de maintenance
|   |-- tests/                # Tests backend
|   `-- pyproject.toml
|
|-- front/
|   |-- api/                  # Proxy Vercel
|   |-- src/                  # Application React
|   |-- package.json
|   |-- package-lock.json
|   `-- vercel.json
|
|-- docs/
|   `-- screenshots/          # Captures d'écran
|
|-- render.yaml
|-- .env.example
`-- README.md
```

---

## 🚀 Installation locale

### Prérequis

Avant de commencer, assurez-vous de disposer de :

- Python 3.11 ou supérieur.
- Node.js 20 ou supérieur.
- npm.
- Git.

Les commandes suivantes sont prévues pour **Windows PowerShell**.

### 1. Cloner le dépôt

```powershell
git clone https://github.com/quentin-charillon/CineQuote-AI.git
cd CineQuote-AI
```

### 2. Installer le backend

```powershell
cd back

py -m venv .venv

.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip

pip install -e ".[dev]"

Copy-Item .env.example .env

python scripts\bootstrap_database.py

uvicorn app.main:app --reload
```

Le script d'initialisation applique les migrations Alembic et importe le catalogue de films.

Le backend est accessible sur :

**http://localhost:8000**

Documentation interactive de l'API :

**http://localhost:8000/docs**

Endpoints de santé :

- `http://localhost:8000/health`
- `http://localhost:8000/health/ready`

### 3. Installer le frontend

Ouvrir un second terminal PowerShell à la racine du projet :

```powershell
cd front

npm ci

Copy-Item .env.example .env

npm run dev
```

Ouvrir ensuite :

**http://localhost:5173**

Le serveur Vite transmet les requêtes `/api` au backend FastAPI local.

---

## 🔐 Configuration et sécurité

Les fichiers d'exemple permettent de configurer l'application :

- `back/.env.example`
- `front/.env.example`
- `.env.example`

Les fichiers `.env` contenant des informations sensibles ne doivent jamais être publiés sur GitHub.

Les secrets doivent rester côté serveur, notamment :

- `GROQ_API_KEY`
- `OPENAI_API_KEY`
- `DATABASE_URL`
- `SESSION_SECRET`
- `PROXY_SHARED_SECRET`

Les variables préfixées par `VITE_` peuvent être intégrées au code envoyé au navigateur. Elles ne doivent donc jamais contenir de secrets.

### Protections implémentées

- Hachage des mots de passe avec PBKDF2-HMAC-SHA256 et sel.
- Jetons d'authentification aléatoires.
- Stockage sécurisé des empreintes de jetons.
- Cookies HTTP-only.
- Cookies `Secure` et `SameSite=Strict` en production.
- Protection contre les requêtes provenant d'origines non autorisées.
- Vérification du secret partagé du proxy.
- Limitation des tentatives de connexion et d'inscription.
- Limitation des appels aux fonctionnalités IA.
- Validation des réponses produites par les modèles.
- Expiration des sessions de quiz inactives.

Les clés API, mots de passe et bonnes réponses ne sont pas volontairement enregistrés dans les journaux applicatifs.

Les sessions actives, certains caches IA et les limites de requêtes sont actuellement conservés en mémoire du processus backend. Cette architecture convient au déploiement initial avec un seul worker.

---

## 🧪 Tests

Le projet possède des tests automatisés pour le backend et le frontend.

### Tests backend

```powershell
cd back

.\.venv\Scripts\python.exe -m pytest
```

### Tests frontend

```powershell
cd front

npm test

npm run typecheck

npm run build
```

Les tests automatisés simulent les fournisseurs d'intelligence artificielle afin d'éviter les appels réels et payants.

### Tests PostgreSQL

Un test d'intégration facultatif peut être exécuté sur une base PostgreSQL dédiée :

```powershell
cd back

$env:TEST_POSTGRES_DATABASE_URL = "postgresql://user:password@localhost:5432/cinequote_test"

.\.venv\Scripts\python.exe -m pytest tests/test_postgres_integration.py

Remove-Item Env:TEST_POSTGRES_DATABASE_URL
```

**Ne jamais exécuter ce test sur la base de données de production.**

---

## 📚 API REST

L'application expose plusieurs endpoints FastAPI.

### Santé du serveur

```http
GET /health
GET /health/ready
```

### Authentification et statistiques

```http
POST /auth/register
POST /auth/login
POST /auth/logout
GET  /auth/me
GET  /stats/me
```

### Intelligence artificielle

```http
POST /ai/coach
POST /ai/recommendations
```

### Quiz

```http
GET  /quiz/sessions/availability
POST /quiz/sessions
POST /quiz/sessions/custom
GET  /quiz/sessions/{id}/question
POST /quiz/sessions/{id}/answers
POST /quiz/sessions/{id}/hint
POST /quiz/sessions/{id}/explanation
GET  /quiz/sessions/{id}/results
```

Les requêtes effectuées depuis le frontend passent par le proxy `/api` de Vercel.

---

## ☁️ Déploiement en production

CineQuote AI est actuellement déployé sur trois services cloud.

### 🌐 Vercel

Le frontend React est hébergé sur Vercel.

**Site public :**

https://cine-quote-ai.vercel.app

Vercel assure :

- La compilation du frontend.
- L'hébergement de l'application web.
- La gestion du domaine HTTPS.
- Le proxy des requêtes API vers Render.

### ⚙️ Render

Le backend FastAPI est hébergé sur Render.

Configuration :

| Paramètre | Valeur |
|---|---|
| Langage | Python 3.12.8 |
| Répertoire racine | `back` |
| Build | `pip install --upgrade pip && pip install .` |
| Démarrage | `python -m scripts.start_production` |
| Health check | `/health/ready` |
| Région | Francfort |
| Workers | 1 |

Au démarrage, le backend vérifie sa configuration, applique les migrations nécessaires et initialise le catalogue.

### 🗄️ Neon

La base de données PostgreSQL de production est hébergée sur **Neon**.

Elle conserve notamment :

- Les comptes utilisateurs.
- Les informations d'authentification persistantes.
- Les films et citations.
- Les statistiques des joueurs.

### 🔄 Mises à jour

Le code source est versionné sur GitHub.

Les services Vercel et Render peuvent être configurés pour déclencher automatiquement un nouveau déploiement après un `git push` sur la branche principale.

Le déploiement automatique de chaque service dépend de sa configuration.

---

## ⚠️ Limites de l'hébergement gratuit

Le projet utilise actuellement des offres d'hébergement gratuites.

Certaines limites doivent être prises en compte :

- **Render :** le backend peut être mis en veille après une période d'inactivité. La première requête peut donc prendre davantage de temps.
- **Neon :** la base PostgreSQL est soumise aux limites de ressources et de stockage du forfait gratuit.
- **Vercel :** les fonctions serverless et la bande passante sont soumises aux quotas du forfait utilisé.
- **GroqCloud :** les appels à l'intelligence artificielle sont soumis aux limites du fournisseur.

Les données persistantes sont conservées dans PostgreSQL, tandis que les sessions de quiz actives en mémoire peuvent être perdues lors d'un redémarrage du backend.

---

## 📝 Gestion du catalogue

Le fichier de référence du catalogue est :

`back/app/data/manual_catalog.json`

Après modification du catalogue en local, il est possible de relancer son import :

```powershell
cd back

.\.venv\Scripts\python.exe scripts\bootstrap_database.py
```

L'import est idempotent afin d'éviter la duplication des données.

Les citations et leurs attributions doivent être vérifiées avant toute utilisation publique ou commerciale, notamment au regard des droits de propriété intellectuelle applicables.

---

## 📄 Licence

Aucune licence logicielle spécifique n'a encore été sélectionnée pour ce projet.

Les titres de films et les extraits de dialogues peuvent être soumis à des droits de propriété intellectuelle distincts de ceux du code source.

---

## 👨‍💻 Développeur

**Quentin Charillon**

Étudiant en 5e année à **Epitech Lyon**, passionné par le développement logiciel, l'intelligence artificielle et le cinéma.

Ce projet me permet de réunir mes centres d'intérêt pour le cinéma et l'IA tout en approfondissant mes compétences en développement full-stack.

**GitHub :** [quentin-charillon](https://github.com/quentin-charillon)

**Application :** [CineQuote AI](https://cine-quote-ai.vercel.app)

---

### 🎬 Prêt à tester vos connaissances ?

**[🍿 Jouer à CineQuote AI](https://cine-quote-ai.vercel.app)**
