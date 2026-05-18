"""Database module for RG_System_Agents (agent classifier model persistence)."""
import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv(
    "AGENT_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/defaultdb"),
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
