"""Client HTTP partagé pour appeler les API tierces.

Un seul client pour toute l'application : il réutilise les connexions déjà
ouvertes (« keep-alive »), ce qui est bien plus rapide que d'en créer une
nouvelle à chaque requête.
"""

import httpx

from app import __version__

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Dépendance FastAPI (remplacée par un faux client dans les tests)."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            # Au-delà de 8 secondes, on abandonne : mieux vaut une source
            # manquante qu'une page bloquée.
            timeout=httpx.Timeout(8.0),
            headers={"User-Agent": f"SuperTracker/{__version__}"},
        )
    return _client


async def close_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
