"""Recherche unifiée et fiches détaillées, avec mise en cache dans Redis.

Pourquoi un cache ? Les API tierces sont lentes (des centaines de
millisecondes), limitent le nombre d'appels autorisés, et leurs données
changent peu. On garde donc chaque réponse quelque temps dans Redis : les
recherches suivantes sont instantanées et ne coûtent rien.
"""

import asyncio
from collections.abc import Awaitable, Callable
from itertools import chain, zip_longest

import httpx
import structlog
from pydantic import TypeAdapter

from app.cache import redis_client
from app.config import get_settings
from app.providers.base import (
    ContentDetail,
    ContentKind,
    MetadataProvider,
    SearchResult,
    Source,
)

log = structlog.get_logger()

CACHE_PREFIX = "cache:"
_results_adapter = TypeAdapter(list[SearchResult])
_detail_adapter = TypeAdapter(ContentDetail | None)


async def cached[T](
    key: str, ttl: int, adapter: TypeAdapter[T], fetch: Callable[[], Awaitable[T]]
) -> T:
    """Renvoie la valeur en cache si elle existe ; sinon la calcule et la range.

    Si Redis est en panne, on continue sans cache : l'application est plus
    lente, mais elle fonctionne (dégradation « gracieuse »).
    """
    full_key = CACHE_PREFIX + key
    try:
        if (raw := await redis_client.get(full_key)) is not None:
            return adapter.validate_json(raw)
    except Exception:
        log.warning("cache.lecture_impossible", key=full_key, exc_info=True)

    value = await fetch()
    try:
        await redis_client.set(full_key, adapter.dump_json(value), ex=ttl)
    except Exception:
        log.warning("cache.ecriture_impossible", key=full_key, exc_info=True)
    return value


def normalize_query(query: str) -> str:
    """« One  PIECE » et « one piece » donnent la même clé de cache."""
    return " ".join(query.lower().split())


async def search_all(
    http: httpx.AsyncClient, providers: list[MetadataProvider], query: str
) -> tuple[list[SearchResult], list[Source]]:
    """Interroge toutes les sources EN PARALLÈLE et fusionne leurs résultats.

    Renvoie les résultats et la liste des sources qui n'ont pas répondu.
    """
    normalized = normalize_query(query)
    ttl = get_settings().search_cache_seconds

    def fetcher(provider: MetadataProvider) -> Callable[[], Awaitable[list[SearchResult]]]:
        return lambda: provider.search(http, normalized)

    # gather lance toutes les requêtes en même temps : la recherche dure le
    # temps de la source la plus lente, pas la somme de toutes.
    outcomes = await asyncio.gather(
        *(
            cached(f"search:{p.source}:{normalized}", ttl, _results_adapter, fetcher(p))
            for p in providers
        ),
        return_exceptions=True,  # une source en panne ne fait pas tout échouer
    )

    lists: list[list[SearchResult]] = []
    unavailable: list[Source] = []
    for provider, outcome in zip(providers, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            log.warning("catalog.source_indisponible", source=provider.source, error=str(outcome))
            unavailable.append(provider.source)
        else:
            lists.append(outcome)

    # Fusion « en alternance » (1er TMDB, 1er AniList, 2e TMDB…) : les
    # meilleurs résultats de chaque source apparaissent en haut de la liste.
    merged = [item for item in chain.from_iterable(zip_longest(*lists)) if item is not None]
    return merged, unavailable


async def get_detail(
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    source: Source,
    kind: ContentKind,
    external_id: str,
) -> ContentDetail | None:
    provider = next((p for p in providers if p.source == source), None)
    if provider is None:
        return None

    detail = await cached(
        f"detail:{source}:{kind}:{external_id}",
        get_settings().detail_cache_seconds,
        _detail_adapter,
        lambda: provider.get_detail(http, kind, external_id),
    )
    return detail
