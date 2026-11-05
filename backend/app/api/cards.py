"""Routes des cartes : collection, ouverture de boosters, fabrication."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, HttpDep, ProvidersDep, SessionDep
from app.core.rate_limit import enforce_rate_limit
from app.models import Rarity
from app.schemas.cards import (
    BoosterOpened,
    CardRead,
    CollectionCard,
    CollectionRead,
    CraftResult,
    DrawnCardRead,
    OpenRequest,
    RarityStat,
    ThemeRead,
)
from app.services import cards as service

router = APIRouter(prefix="/cards", tags=["Cartes"])


@router.get("/me", summary="Ma collection, mes boosters, mes fragments")
async def my_collection(
    user: CurrentUser, session: SessionDep, http: HttpDep, providers: ProvidersDep
) -> CollectionRead:
    await service.sync_boosters(session, user.id)  # bienvenue, niveaux, minuteur
    # Vos contenus suivis rejoignent le catalogue de cartes.
    await service.refresh_cards(session, http, providers, user.id)
    entries = await service.collection(session, user.id)
    wallet = await service.wallet_state(session, user.id)
    owned, totals, themes = await service.catalog_stats(session, user.id)
    total_weight = sum(service.WEIGHTS.values())
    return CollectionRead(
        boosters=await service.count_boosters(session, user.id),
        fragments=wallet.fragments,
        boosters_until_pity=service.PITY_BOOSTERS - wallet.boosters_since_epic,
        next_free_booster_in=await service.timer_status(session, user.id),
        free_booster_minutes=service.TIMER_SECONDS // 60,
        free_booster_max_stock=service.TIMER_MAX_STOCK,
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
        cards=[
            CollectionCard(
                **CardRead.of(e.card, e.content).model_dump(),
                owned=e.owned,
                craft_cost=service.CRAFT_COST.get(Rarity(e.card.rarity)),
            )
            for e in entries
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
    theme = body.theme if body else service.PackTheme.MIXED
    await service.sync_boosters(session, user.id)
    try:
        result = await service.open_booster(session, http, providers, user.id, theme)
    except service.NoBoosterError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Vous n'avez aucun booster à ouvrir."
        ) from None
    except service.EmptyPoolError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Les cartes de ce thème sont en préparation. Réessayez dans quelques minutes.",
        ) from None
    return BoosterOpened(
        theme=result.theme,
        cards=[
            DrawnCardRead(
                card=CardRead.of(d.card, d.content), is_new=d.is_new, fragments=d.fragments
            )
            for d in result.cards
        ],
        fragments=result.fragments,
        boosters_left=result.boosters_left,
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
        card, content, fragments = await service.craft(session, user.id, card_id)
    except service.CardNotAvailableError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Cette carte ne peut pas être fabriquée."
        ) from None
    except service.AlreadyOwnedError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous avez déjà cette carte.") from None
    except service.NotEnoughFragmentsError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pas assez de fragments.") from None
    return CraftResult(card=CardRead.of(card, content), fragments=fragments)
