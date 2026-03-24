"""
Database configuration and session management.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from loguru import logger

from app.core.config import settings

# Convert sync URL to async
DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def init_db():
    """Initialize database and create tables."""
    # Import models to ensure they are registered with Base.metadata
    import app.models  # noqa

    async with engine.begin() as conn:
        # Enable TimescaleDB extension
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
            logger.info("TimescaleDB extension enabled")
        except Exception as e:
            logger.warning(f"Could not enable TimescaleDB: {e}")

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_db_connection():
    """
    Get a synchronous database connection for non-async contexts.
    Used by services that need sync DB access (e.g., Celery tasks, bots).

    Returns a psycopg2 connection or None on failure.
    """
    import psycopg2
    from urllib.parse import urlparse

    try:
        # Parse the async URL and convert to sync
        url = settings.DATABASE_URL
        parsed = urlparse(url)

        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path[1:],  # Remove leading /
            user=parsed.username,
            password=parsed.password
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to create sync DB connection: {e}")
        return None
