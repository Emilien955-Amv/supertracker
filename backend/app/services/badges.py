"""Catalogue des succès.

Chaque succès est une simple donnée : une mesure (« metric »), un seuil et
une récompense. Ajouter un succès = ajouter une ligne ici, sans toucher au
reste du code. Les mesures sont calculées dans services/gamification.py.
"""

from dataclasses import dataclass
from enum import StrEnum


class Tier(StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


# XP offerts au déblocage, selon le palier.
TIER_XP = {Tier.BRONZE: 20, Tier.SILVER: 50, Tier.GOLD: 100}


class Metric(StrEnum):
    EPISODES = "episodes"  # épisodes vus (hors épisodes spéciaux)
    ANIME_EPISODES = "anime_episodes"
    MOVIES = "movies"  # films vus
    SERIES_COMPLETED = "series_completed"  # séries et animes terminés
    REVIEWS = "reviews"  # avis écrits
    LIBRARIES = "libraries"
    STREAK = "streak"  # jours d'affilée avec au moins un visionnage
    MARATHONS = "marathons"
    JOUR_J = "jour_j"  # épisodes vus le jour de leur sortie
    LEVEL = "level"


@dataclass(frozen=True)
class Badge:
    code: str
    name: str
    description: str
    icon: str  # émoji : lisible partout, sans fichier image à héberger
    tier: Tier
    metric: Metric
    threshold: int


BADGES: tuple[Badge, ...] = (
    Badge(
        "premier_pas",
        "Premier pas",
        "Regarder un premier épisode.",
        "👣",
        Tier.BRONZE,
        Metric.EPISODES,
        1,
    ),
    Badge(
        "binge_100",
        "Binge-watcheur",
        "Regarder 100 épisodes.",
        "🍿",
        Tier.SILVER,
        Metric.EPISODES,
        100,
    ),
    Badge(
        "binge_1000",
        "Légende du canapé",
        "Regarder 1 000 épisodes.",
        "🛋️",
        Tier.GOLD,
        Metric.EPISODES,
        1000,
    ),
    Badge(
        "otaku",
        "Otaku",
        "Regarder 50 épisodes d'anime.",
        "🍥",
        Tier.SILVER,
        Metric.ANIME_EPISODES,
        50,
    ),
    Badge("cinephile", "Cinéphile", "Voir 10 films.", "🎬", Tier.BRONZE, Metric.MOVIES, 10),
    Badge("cinephile_50", "Cinémathèque", "Voir 50 films.", "🎞️", Tier.GOLD, Metric.MOVIES, 50),
    Badge(
        "fin_de_saga",
        "Fin de saga",
        "Terminer une série.",
        "🏁",
        Tier.BRONZE,
        Metric.SERIES_COMPLETED,
        1,
    ),
    Badge(
        "collectionneur",
        "Finisseur",
        "Terminer 10 séries.",
        "🏆",
        Tier.GOLD,
        Metric.SERIES_COMPLETED,
        10,
    ),
    Badge("critique", "Critique", "Écrire 5 avis.", "✍️", Tier.BRONZE, Metric.REVIEWS, 5),
    Badge(
        "bibliothecaire",
        "Bibliothécaire",
        "Créer 3 bibliothèques.",
        "📚",
        Tier.BRONZE,
        Metric.LIBRARIES,
        3,
    ),
    Badge(
        "regulier", "Régulier", "Regarder 7 jours d'affilée.", "🔥", Tier.SILVER, Metric.STREAK, 7
    ),
    Badge(
        "marathonien",
        "Marathonien",
        "Regarder 5 épisodes dans la journée.",
        "🏃",
        Tier.BRONZE,
        Metric.MARATHONS,
        1,
    ),
    Badge(
        "jour_j",
        "Jour J",
        "Voir un épisode le jour de sa sortie.",
        "📅",
        Tier.SILVER,
        Metric.JOUR_J,
        1,
    ),
    Badge("niveau_10", "Vétéran", "Atteindre le niveau 10.", "⭐", Tier.GOLD, Metric.LEVEL, 10),
)

BADGES_BY_CODE = {badge.code: badge for badge in BADGES}
