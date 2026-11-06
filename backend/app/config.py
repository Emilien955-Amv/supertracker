"""Configuration de l'application, lue depuis les variables d'environnement.

Principe « 12-factor » : le même code tourne en développement, en recette
et en production ; seules les variables d'environnement changent. Aucun
secret n'est donc écrit en dur dans le code.
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valeur utilisable UNIQUEMENT en local : le démarrage est refusé si elle est
# encore présente en recette ou en production (voir le validateur plus bas).
DEV_JWT_SECRET = "dev-only-secret-a-changer-0123456789abcdef"  # noqa: S105 (volontaire)


class Settings(BaseSettings):
    """Paramètres validés par Pydantic : une valeur invalide fait échouer
    le démarrage immédiatement, plutôt qu'une erreur obscure plus tard."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SuperTracker"
    environment: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/supertracker"
    redis_url: str = "redis://localhost:6379/0"

    # --- Authentification ---
    # Clé secrète qui signe les jetons d'accès. Qui la connaît peut fabriquer
    # de faux jetons : elle doit rester secrète et longue (32 caractères min).
    jwt_secret: str = DEV_JWT_SECRET
    # Jeton d'accès court : s'il est volé, il ne sert que quelques minutes.
    access_token_minutes: int = 15
    # Jeton de renouvellement long : il évite de se reconnecter chaque jour.
    refresh_token_days: int = 30
    # En production (HTTPS), le cookie ne doit jamais circuler en clair.
    cookie_secure: bool = False

    # --- Sources de données externes ---
    # Vide = TMDB désactivé (la recherche fonctionne alors avec AniList seul).
    tmdb_api_token: str = ""
    # Durées de mise en cache des réponses des API tierces, en secondes.
    search_cache_seconds: int = 3600  # 1 h : les résultats bougent peu
    detail_cache_seconds: int = 86400  # 24 h : une fiche change rarement
    # Votes nécessaires pour qu'une œuvre demandée entre au catalogue de cartes.
    card_request_votes: int = 3

    # Base dédiée aux tests (en local) : les tests ne touchent jamais aux
    # données de développement, ni à la tâche qui remplit le catalogue de cartes.
    test_database_url: str = ""

    @model_validator(mode="after")
    def _base_de_test(self) -> "Settings":
        if self.environment == "test" and self.test_database_url:
            self.database_url = self.test_database_url
        return self

    @model_validator(mode="after")
    def _verifier_secrets(self) -> "Settings":
        if self.environment in ("staging", "production"):
            if self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET doit être défini (32 caractères minimum).")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE doit valoir true hors développement.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Renvoie toujours la même instance (lue une seule fois au démarrage)."""
    return Settings()
