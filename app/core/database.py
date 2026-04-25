from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# ── Async engine — used by FastAPI endpoints ──────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,          # set True to see SQL queries in terminal
    pool_pre_ping=True,  # reconnect if connection dropped
)

# ── Session factory ───────────────────────────────────────
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Base class for all models ─────────────────────────────
Base = declarative_base()


# ── Dependency — inject DB session into routes ────────────
async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides a database session.
    Use with: db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise