# SuperTracker

Application web et mobile (PWA) de suivi de séries, animes, films, livres et
jeux vidéo, avec bibliothèques personnalisées, gamification et cartes à
collectionner.

> **État actuel : étape 1c.** Comptes utilisateurs sécurisés, recherche unifiée de films,
> séries et animes (TMDB, AniList) avec fiche détaillée, « où regarder » (logos cliquables) et cache Redis ;
> suivi (statut, note, avis), épisodes cochés un par un avec progression, et
> bibliothèques personnelles colorées (grille, étagère ou liste ; tri au choix).

---

## 1. Installer les outils (une seule fois)

| Outil | Rôle | Téléchargement |
|---|---|---|
| **Docker Desktop** | Fait tourner toute l'application dans des conteneurs | https://www.docker.com/products/docker-desktop/ |
| **Git** | Gestion des versions du code | https://git-scm.com/ (déjà installé chez vous) |
| **VS Code** | Éditeur de code | https://code.visualstudio.com/ |

Sous Windows, Docker Desktop vous proposera d'activer **WSL 2** : acceptez, puis
redémarrez l'ordinateur. Vérifiez ensuite dans un terminal :

```bash
docker --version
docker compose version
```

Python et Node.js ne sont **pas obligatoires** sur votre machine : ils sont
installés à l'intérieur des conteneurs.

## 2. Lancer l'application

Dans un terminal, depuis le dossier `supertracker` :

```bash
cp .env.example .env
docker compose up --build
```

**Recherche de films et séries (facultatif)** : ajoutez votre jeton TMDB dans .env
(`TMDB_API_TOKEN=eyJ…`, à obtenir gratuitement sur themoviedb.org → Paramètres → API →
« Jeton d'accès en lecture »). Sans lui, la recherche fonctionne avec les animes AniList seuls.

Le premier lancement prend quelques minutes (téléchargement des images). Ensuite :

| Adresse | Contenu |
|---|---|
| http://localhost:5173 | L'application (frontend React) |
| http://localhost:8000/api/docs | La documentation interactive de l'API (Swagger) |
| http://localhost:8000/api/health | L'état de santé de l'API, en JSON |

Pour arrêter : `Ctrl + C`, puis `docker compose down`.
Pour tout effacer, **y compris la base de données** : `docker compose down -v`.

## 3. Lancer les tests

Pendant que `docker compose up` tourne, dans un **second** terminal :

```bash
docker compose exec -e ENVIRONMENT=test api pytest --cov
docker compose exec api ruff check .
docker compose exec api mypy app
docker compose exec web npm test
docker compose exec web npm run lint
```

## 4. Commandes utiles au quotidien

| Besoin | Commande |
|---|---|
| Voir les journaux de l'API | `docker compose logs -f api` |
| Ouvrir un terminal dans le conteneur API | `docker compose exec api bash` |
| Créer une migration après avoir modifié un modèle | `docker compose exec api alembic revision --autogenerate -m "description"` |
| Appliquer les migrations | `docker compose exec api alembic upgrade head` |
| Ouvrir la base en ligne de commande | `docker compose exec db psql -U supertracker` |
| Reformater le code Python | `docker compose exec api ruff format .` |
| Ajouter une dépendance npm | `docker compose exec web npm install <paquet>` |

## 5. Organisation du projet

```
supertracker/
├── docker-compose.yml      Environnement local complet
├── .env.example            Modèle de configuration (copier en .env)
├── .github/workflows/      Intégration continue (GitHub Actions)
├── backend/                API Python FastAPI
│   ├── app/
│   │   ├── main.py         Point d'entrée de l'API
│   │   ├── config.py       Configuration (variables d'environnement)
│   │   ├── db.py           Connexion PostgreSQL
│   │   ├── cache.py        Connexion Redis
│   │   ├── logging.py      Journaux structurés
│   │   ├── api/            Routes HTTP (une par domaine fonctionnel)
│   │   └── models/         Tables de la base de données
│   ├── alembic/versions/   Migrations versionnées
│   └── tests/              Tests automatisés (pytest)
└── frontend/               Application React (PWA)
    ├── src/App.tsx         Page d'accueil
    └── public/icon.svg     Icône de l'application
```

## 6. Publier sur GitHub (et déclencher la CI)

1. Créez un dépôt **vide** sur https://github.com/new, nommé `supertracker`.
2. Depuis le dossier `supertracker` :

```bash
git init -b main
git add .
git commit -m "Étape 0 : socle du projet"
git remote add origin https://github.com/<votre-pseudo>/supertracker.git
git push -u origin main
```

3. Ouvrez l'onglet **Actions** du dépôt : les trois tâches (backend, frontend,
   Docker) doivent passer au vert.

Pensez aussi à générer et versionner `frontend/package-lock.json`, qui fige
les versions exactes des dépendances (le dossier `frontend` étant monté dans le
conteneur, le fichier apparaît directement sur votre disque) :

```bash
docker compose run --rm web npm install
git add frontend/package-lock.json
git commit -m "Ajout du package-lock"
```
