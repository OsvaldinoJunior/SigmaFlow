"""
Database connection and session management.
Supports both sync (for Celery workers) and async (for FastAPI) patterns.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from sigmaflow.core.config import get_settings
from sigmaflow.core.models import Base

settings = get_settings()

# ── Sync engine (for Celery workers, migrations, scripts) ─────────────────────

_sync_engine = None
_SessionLocal: Optional[sessionmaker] = None


def get_sync_engine():
    """Get or create the synchronous database engine."""
    global _sync_engine
    if _sync_engine is None:
        # Ensure data directory exists for SQLite
        from pathlib import Path
        db_url = settings.database_url_sync
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        _sync_engine = create_engine(
            settings.database_url_sync,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            echo=settings.db_echo,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        # Enable UUID extension on connect (PostgreSQL only)
        @event.listens_for(_sync_engine, "connect")
        def _enable_uuid(dbapi_conn, connection_record):
            # Only for PostgreSQL - SQLite doesn't need this and cursor doesn't support context manager
            if _sync_engine.dialect.name == "postgresql":
                cur = dbapi_conn.cursor()
                cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
                cur.close()
    return _sync_engine


def get_session_factory() -> sessionmaker:
    """Get the sync session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_sync_engine(),
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _SessionLocal


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """
    Context manager for synchronous database sessions.
    Use in Celery tasks, scripts, and synchronous code.

    Usage:
        with get_sync_session() as session:
            session.add(obj)
            session.commit()
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_sync_session_direct() -> Session:
    """
    Get a sync session directly (caller must manage commit/rollback/close).
    For cases where context manager doesn't fit.
    """
    return get_session_factory()()


# ── Async engine (for FastAPI) ────────────────────────────────────────────────

_async_engine = None
_AsyncSessionLocal: Optional[async_sessionmaker] = None


def get_async_engine():
    """Get or create the asynchronous database engine."""
    global _async_engine
    if _async_engine is None:
        # Ensure data directory exists for SQLite
        from pathlib import Path
        db_url = settings.database_url_async
        if db_url.startswith("sqlite+aiosqlite:///"):
            db_path = db_url.replace("sqlite+aiosqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        _async_engine = create_async_engine(
            settings.database_url_async,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            echo=settings.db_echo,
            pool_pre_ping=True,
            pool_recycle=3600,
            # NullPool for serverless / testing
            # poolclass=NullPool,
        )
    return _async_engine


def get_async_session_factory() -> async_sessionmaker:
    """Get the async session factory."""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _AsyncSessionLocal


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for asynchronous database sessions.
    Use with Depends() in FastAPI route handlers.

    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    factory = get_async_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def get_async_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for asynchronous database sessions.
    Use for manual session management (not FastAPI Depends).

    Usage:
        async with get_async_session_context() as session:
            ...
    """
    factory = get_async_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ── Database initialization ──────────────────────────────────────────────────

def init_db(drop_first: bool = False) -> None:
    """
    Initialize database tables.
    In production, use Alembic migrations instead.
    """
    engine = get_sync_engine()
    if drop_first:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


async def init_db_async(drop_first: bool = False) -> None:
    """Initialize database tables using async engine."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        if drop_first:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


def drop_db() -> None:
    """Drop all database tables (dev/testing only)."""
    engine = get_sync_engine()
    Base.metadata.drop_all(engine)


def check_db_connection() -> bool:
    """Check if database is reachable."""
    try:
        engine = get_sync_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_db_connection_async() -> bool:
    """Check if database is reachable (async)."""
    try:
        engine = get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ── Cleanup ───────────────────────────────────────────────────────────────────

def close_db_connections() -> None:
    """Close all database connections. Call on application shutdown."""
    global _sync_engine, _async_engine, _SessionLocal, _AsyncSessionLocal
    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None
    if _async_engine:
        # Async engine disposal is async, schedule it
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_async_engine.dispose())
            else:
                loop.run_until_complete(_async_engine.dispose())
        except RuntimeError:
            pass  # No event loop
        _async_engine = None
    _SessionLocal = None
    _AsyncSessionLocal = None