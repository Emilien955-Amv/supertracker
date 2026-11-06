"""Routes des cartes : collection, ouverture de boosters, fabrication."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, HttpDep, ProvidersDep, SessionDep
from app.core.rate_limit import enforce_rate_limit
from app.models import Content, Rarity
from app.providers.base import ContentKind, Source
from app.schemas.cards import (
    BinderContent,
    BinderEntryRead,
    BinderPageRead,
    BoosterOpened,
    CardRead,
    CollectionCard,
    CollectionRead,
    CraftResult,
    DrawnCardRead,
    MasteryRead,
    OpenRequest,
    PackContents,
    RarityCount,
    RarityStat,
    RecycleRequest,
    RecycleResult,
    ThemeRead,
)
from app.schemas.gamification import RewardsRead
from app.services import cards as service
from app.services.gamification import Rewards
from app.services.titles import title_for

router = APIRouter(prefix="/cards", tags=["Cartes"])


@router.get("/me", summary="Ma collection, mes boosters, mes fragments")
async def my_collection(
    user: CurrentUser, session: SessionDep, http: HttpDep, providers: ProvidersDep
) -> CollectionRead:
    await service.sync_boosters(session, user.id)  # bienvenue, niveaux, minuteur
    wallet = await service.wallet_state(session, user.id)
    owned, totals, themes = await service.catalog_stats(session, user.id)
    duplicates, duplicates_value = await service.duplicates_summary(session, user.id)
    total_weight = sum(service.WEIGHTS.values())
    return CollectionRead(
        boosters=await service.count_boosters(session, user.id),
        fragments=wallet.fragments,
        boosters_until_pity=service.PITY_BOOSTERS - wallet.boosters_since_epic,
        next_free_booster_in=await service.timer_status(session, user.id),
        free_booster_minutes=service.TIMER_SECONDS // 60,
        free_booster_max_stock=service.TIMER_MAX_STOCK,
        duplicates=duplicates,
        duplicates_value=duplicates_value,
        themes=[
            ThemeRead(theme=theme, label=service.THEME_LABELS[theme], cards=themes[theme])
            for theme in service.PackTheme
        ],
        stats=[
            RarityStat(
                rarity=rarity,
                owned=owned.get(rarity, 0),
                total=totals.get(rarity, 0),
                chance_percent=round(100 * service.WEIGHTS[rarity] / total_weight, 1),
            )
            for rarity in Rarity
        ],
    )


def _binder_content(content: Content) -> BinderContent:
    return BinderContent(
        id=content.id,
        source=Source(content.source),
        kind=ContentKind(content.kind),
        external_id=content.external_id,
        title=content.title,
        poster_url=content.poster_url,
        year=content.year,
    )


def _mastery(
    content: Content, completed_at: datetime | None = None, rewards: Rewards | None = None
) -> MasteryRead:
    return MasteryRead(
        content_id=content.id,
        work_title=content.title,
        poster_url=content.poster_url,
        title=title_for(content.title),
        completed_at=completed_at,
        rewards=RewardsRead.of(rewards) if rewards else None,
    )


def _new_masteries(masteries: list[service.MasteryResult]) -> list[MasteryRead]:
    return [_mastery(m.content, rewards=m.rewards) for m in masteries]


@router.get("/binder", summary="Mon classeur : une pochette par œuvre")
async def my_binder(user: CurrentUser, session: SessionDep) -> list[BinderEntryRead]:
    mastered = {c.id for _, c in await service.masteries_of(session, user.id)}
    return [
        BinderEntryRead(
            content=_binder_content(e.content),
            owned=e.owned,
            total=e.total,
            mastered=e.content.id in mastered,
        )
        for e in await service.binder(session, user.id)
    ]


@router.get("/masteries", summary="Mes collections complètes (cartes « Maître » et titres)")
async def my_masteries(user: CurrentUser, session: SessionDep) -> list[MasteryRead]:
    return [_mastery(c, m.completed_at) for m, c in await service.masteries_of(session, user.id)]


@router.get(
    "/binder/{content_id}",
    summary="Toutes les cartes d'une œuvre",
    responses={404: {"description": "Œuvre introuvable"}},
)
async def binder_page(user: CurrentUser, session: SessionDep, content_id: int) -> BinderPageRead:
    page = await service.binder_page(session, user.id, content_id)
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Œuvre introuvable.")
    content, entries = page
    wallet = await service.wallet_state(session, user.id)
    mastery = next(
        (m for m, c in await service.masteries_of(session, user.id) if c.id == content.id), None
    )
    return BinderPageRead(
        content=_binder_content(content),
        mastery=_mastery(content, mastery.completed_at) if mastery else None,
        fragments=wallet.fragments,
        cards=[
            CollectionCard(
                **CardRead.of(e.card, e.content).model_dump(),
                owned=e.owned,
                copies=e.copies,
                craft_cost=service.CRAFT_COST.get(Rarity(e.card.rarity)),
            )
            for e in entries
        ],
    )


@router.get("/packs/{theme}", summary="Cartes qu'on peut obtenir dans un pack")
async def pack_contents(
    user: CurrentUser,
    session: SessionDep,
    theme: service.PackTheme,
    rarity: Rarity | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Personnage ou œuvre")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 60,
) -> PackContents:
    page = await service.pack_cards(
        session, user.id, theme, rarity, (q or "").strip() or None, offset, limit
    )
    return PackContents(
        theme=theme,
        label=service.THEME_LABELS[theme],
        total=page.total,
        matching=page.matching,
        rarities=[RarityCount(rarity=r, count=page.by_rarity.get(r, 0)) for r in Rarity],
        cards=[
            CollectionCard(
                **CardRead.of(e.card, e.content).model_dump(),
                owned=e.owned,
                copies=e.copies,
                craft_cost=service.CRAFT_COST.get(Rarity(e.card.rarity)),
            )
            for e in page.entries
        ],
    )


@router.post(
    "/boosters/open",
    summary="Ouvrir un booster de 5 cartes du thème choisi",
    responses={409: {"description": "Aucun booster, ou thème sans cartes"}},
)
async def open_booster(
    user: CurrentUser,
    session: SessionDep,
    http: HttpDep,
    providers: ProvidersDep,
    body: OpenRequest | None = None,
) -> BoosterOpened:
    await enforce_rate_limit(f"booster:{user.id}", limit=60, window_seconds=60)
    request = body or OpenRequest()
    await service.sync_boosters(session, user.id)
    results: list[service.OpenResult] = []
    try:
        for _ in range(request.count):
            results.append(
                await service.open_booster(session, http, providers, user.id, request.theme)
            )
    except service.NoBoosterError:
        if not results:  # plus de booster en cours de route : on garde ceux ouverts
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Vous n'avez aucun booster à ouvrir."
            ) from None
    except service.EmptyPoolError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Les cartes de ce thème sont en préparation. Réessayez dans quelques minutes.",
        ) from None
    return BoosterOpened(
        theme=request.theme,
        boosters_opened=len(results),
        cards=[
            DrawnCardRead(
                card=CardRead.of(d.card, d.content), is_new=d.is_new, fragments=d.fragments
            )
            for result in results
            for d in result.cards
        ],
        fragments=results[-1].fragments,
        boosters_left=results[-1].boosters_left,
        masteries=[m for result in results for m in _new_masteries(result.masteries)],
    )


@router.post(
    "/{card_id}/craft",
    summary="Fabriquer une carte avec des fragments",
    responses={
        404: {"description": "Carte introuvable ou non fabricable"},
        409: {"description": "Refusé"},
    },
)
async def craft(user: CurrentUser, session: SessionDep, card_id: int) -> CraftResult:
    try:
        card, content, fragments, masteries = await service.craft(session, user.id, card_id)
    except service.CardNotAvailableError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Cette carte ne peut pas être fabriquée."
        ) from None
    except service.AlreadyOwnedError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous avez déjà cette carte.") from None
    except service.NotEnoughFragmentsError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pas assez de fragments.") from None
    return CraftResult(
        card=CardRead.of(card, content), fragments=fragments, masteries=_new_masteries(masteries)
    )


@router.post("/recycle-duplicates", summary="Recycler tous mes doublons en fragments")
async def recycle_all(user: CurrentUser, session: SessionDep) -> RecycleResult:
    recycled, gained, fragments = await service.recycle(session, user.id)
    return RecycleResult(recycled=recycled, gained=gained, fragments=fragments)


@router.post(
    "/{card_id}/recycle", summary="Recycler des doublons d'une carte (un exemplaire reste)"
)
async def recycle_one(
    user: CurrentUser, session: SessionDep, card_id: int, body: RecycleRequest | None = None
) -> RecycleResult:
    count = body.count if body else 1
    recycled, gained, fragments = await service.recycle(session, user.id, card_id, count)
    return RecycleResult(recycled=recycled, gained=gained, fragments=fragments)
