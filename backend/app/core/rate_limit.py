"""Limitation du débit des requêtes, stockée dans Redis.

Principe de la « fenêtre fixe » : on compte les tentatives dans une clé Redis
qui s'efface d'elle-même au bout de la fenêtre (par ex. 15 minutes). Au-delà
de la limite, l'API répond 429 « Too Many Requests ».

Redis est partagé par toutes les instances de l'API : la limite reste
correcte même quand plusieurs conteneurs tournent en parallèle.
"""

from fastapi import HTTPException, status

from app.cache import redis_client

KEY_PREFIX = "ratelimit:"


async def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Compte une tentative pour « key » et lève une erreur 429 si la limite
    est dépassée."""
    full_key = KEY_PREFIX + key
    count = await redis_client.incr(full_key)
    if count == 1:
        # Première tentative de la fenêtre : on programme l'effacement.
        await redis_client.expire(full_key, window_seconds)

    if count > limit:
        retry_after = await redis_client.ttl(full_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Réessayez dans quelques minutes.",
            headers={"Retry-After": str(max(retry_after, 1))},
        )
