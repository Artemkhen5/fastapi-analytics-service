import os
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://analytics_test:analytics_password@127.0.0.1:5433/analytics_test",
)

if make_url(TEST_DATABASE_URL).database != "analytics_test":
    raise RuntimeError("Tests must use the analytics_test database")

# Tests import application modules during collection, before fixtures run.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


@pytest_asyncio.fixture
async def test_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(TEST_DATABASE_URL)

    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()

            try:
                yield async_sessionmaker(
                    bind=connection,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
