"""Connexion à PostgreSQL via SQLAlchemy en mode asynchrone."""

from collections.abc import AsyncIterator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

# Convention de nommage des contraintes : Alembic génère ainsi des noms
# stables et lisibles (ex. « uq_users_email ») au lieu de noms aléatoires,
# ce qui rend les migrations reproductibles d'un environnement à l'autre.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Classe mère de tous les modèles (tables) de l'application."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# En test, on désactive le « pool » de connexions : chaque test ouvre et
# ferme sa propre connexion, ce qui évite les conflits entre boucles asyncio.
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    poolclass=NullPool if settings.environment == "test" else None,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dépendance FastAPI : fournit une session par requête, puis la ferme."""
    async with SessionLocal() as session:
        yield session
