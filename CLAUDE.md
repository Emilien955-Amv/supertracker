# SuperTracker — mémoire du projet

Application web/mobile (PWA) de suivi de séries, animes, films (puis livres et
jeux), avec gamification et cartes à collectionner. Projet personnel d'Emilien
(débutant, formation Cloud & DevOps), budget cloud ~10 €/mois.

## Façon de travailler

- **Tout en français** : réponses, interface, commentaires du code, messages de commit.
- Utilisateur débutant : expliquer simplement, étape par étape, avec un résumé à la fin.
- Code complet et testé à chaque étape ; commit + push + CI verte avant de rendre la main.
- Docker : **une seule personne lance `docker compose` à la fois** (prévenir avant).
- Secrets : la clé TMDB est dans `.env` (jamais affichée, jamais commitée).
- Comptes de test temporaires (`essai_*`) : toujours supprimés après vérification.

## Pile technique

- Backend : Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL 16, Redis 7.
- Frontend : React 19, Vite 7, TypeScript, Tailwind v4, react-router 7, dnd-kit.
- Sources : TMDB (films, séries, « où regarder » via JustWatch), AniList (animes,
  personnages dessinés), Disney API (dessins des personnages d'animation Disney).

## Commandes utiles

```bash
docker compose up -d
docker compose exec -e ENVIRONMENT=test api sh -c "alembic upgrade head && pytest"   # base supertracker_test
docker compose exec api sh -c "ruff format . && ruff check . && mypy app"
docker compose exec web sh -c "npm run lint && npx tsc -b && npm test"
docker compose exec api python -m app.services.card_catalog   # remplir le catalogue de cartes
```

Les tests backend utilisent la base dédiée `supertracker_test` (créée une fois avec
`docker compose exec db createdb -U supertracker supertracker_test`).

## Règles de jeu décidées

- **XP** : 10/épisode, 50/film, +100 série terminée, Jour J +25, marathon +40,
  série de jours +5 %/jour (max +50 %), plafond 300 XP de visionnage par jour,
  rien pour un contenu pas sorti, décocher reprend les XP. 14 succès.
- **Niveaux** : XP nécessaire = 100 × (niveau − 1)^1,5.
- **Cartes** : uniquement des personnages (jamais d'acteurs ni de doubleurs).
  Raretés par rang d'importance : n° 1 Divine (une par œuvre, non fabricable),
  n° 2 Mythique, n° 3-4 Légendaires, puis Épique (rôles principaux), Rare
  (seconds rôles), Peu commune (récurrents), Commune (petits rôles).
  Probabilités : 50 / 25 / 13 / 7 / 3,5 / 1 / 0,5 %. Rare garantie par booster,
  Épique+ garantie au 20e booster sans.
- **Boosters** : bienvenue, 1 toutes les 5 min (12 en réserve max), 1 par niveau,
  1 par film/série/anime terminé. Packs par genre et par plateforme.
  Doublons → fragments → fabrication.
- **Animes** : saisons AniList regroupées en une œuvre ; animes japonais
  uniquement via AniList.
- **Profils** privés par défaut (RGPD), visibles des amis ou de tous si public.

## Feuille de route

Fait : socle, comptes, recherche + où regarder, suivi + bibliothèques (meuble à
étagères), XP/succès, cartes, profils et amis (3a), catalogue resserré (100 séries,
100 films dont sagas, 100 animes ; personnages de toutes les saisons, max 300),
collections complètes (carte « Maître », titre, 500 XP, 5 boosters, succès),
sondages (3 votes → l'œuvre entre au catalogue).

À faire, dans l'ordre (décidé le 2026-11-06) :

1. ✅ **Catalogue de cartes resserré** : 100 séries, 100 films (sagas regroupées :
   « Harry Potter » = une seule œuvre), 100 animes les plus populaires, avec le
   maximum de personnages (One Piece, Naruto… jusqu'à 300). Récompense quand une
   œuvre est complétée en cartes (décidé : les quatre à la fois) : carte « Maître »
   dorée unique à l'œuvre, titre de profil (ex. « Roi des pirates »), boosters +
   XP bonus, succès spécial. **Sondages** : les utilisateurs demandent et votent
   pour les œuvres à ajouter au catalogue.
2. **Échange de cartes** (3b) : garder ses doublons, les recycler en fragments à
   la demande, proposer des échanges entre amis.
3. **Accueil personnalisé** : suggestions du jour selon les goûts (changent chaque
   jour, jamais déjà vues), « À voir ce soir ». Visuel amélioré.
4. **Recherche avancée** (filtres genre, année, type, plateforme, note…) et
   **visuel du suivi** amélioré.
5. **Paramètres** façon TV Time / Sofa Time (pays des plateformes, spoilers,
   notifications, thème, format de note…).
6. **Pièce 3D « façon IKEA »** : configurer une pièce, placer plusieurs meubles,
   ranger ses œuvres comme ses CD ; comparer les bibliothèques entre amis.
7. **Ouverture des cartes** plus spectaculaire.
8. **Livres et jeux vidéo** (nouvelles sources de données).
9. Puis : calendrier des sorties et alertes, mise en ligne (Hetzner + k3s,
   Terraform, Argo CD, supervision, sauvegardes), RGPD, import TV Time.

## Points en suspens

- Suivi de One Piece fait sur la fiche TMDB (anime) : à transférer vers la fiche AniList.
- Pixar / DreamWorks : pas encore de dessins de personnages (seulement Disney).
- Connexion aux plateformes : impossible directement ; pistes = import de
  l'historique Netflix (CSV) et extension de navigateur.
