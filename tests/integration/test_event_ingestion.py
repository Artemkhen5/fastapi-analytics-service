import json
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.events.models import Event, EventReceipt
from src.rabbit.exceptions import PermanentProcessingError
from src.rabbit.payload import calculate_payload_hash
from src.rabbit.service import RabbitService


@pytest.mark.asyncio
async def test_saves_event_and_receipt(
        test_session_factory: async_sessionmaker[AsyncSession],
        uuid_v_7: str,
) -> None:
    event_id = UUID(uuid_v_7)
    body = json.dumps({
        "event_id": str(event_id),
        "event_type": "task_event",
        "event_date": "2026-09-01T10:00:00Z",
    }).encode("utf-8")

    service = RabbitService(test_session_factory)
    await service.handle_message(body)

    async with test_session_factory() as session:
        event = await session.get(Event, event_id)
        receipt = await session.get(EventReceipt, event_id)

    assert event is not None
    assert event.event_type == "task_event"
    assert receipt is not None


@pytest.mark.asyncio
async def test_repeated_message_does_not_create_duplicates(
        test_session_factory: async_sessionmaker[AsyncSession],
        uuid_v_7: str,
) -> None:
    event_id = UUID(uuid_v_7)
    body = json.dumps({
        "event_id": uuid_v_7,
        "event_type": "task_event",
        "event_date": "2026-09-01T10:00:00Z",
    }).encode("utf-8")

    service = RabbitService(test_session_factory)
    await service.handle_message(body)
    await service.handle_message(body)

    async with test_session_factory() as session:
        event_count = await session.scalar(
            select(func.count()).select_from(Event).where(Event.id == event_id)
        )
        receipt_count = await session.scalar(
            select(func.count()).select_from(EventReceipt).where(
                EventReceipt.event_id == event_id
            )
        )

    assert event_count == 1
    assert receipt_count == 1


@pytest.mark.asyncio
async def test_same_event_id_with_different_payload_is_conflict(
        test_session_factory: async_sessionmaker[AsyncSession],
        uuid_v_7: str,
) -> None:
    event_id = UUID(uuid_v_7)
    original_body = json.dumps({
        "event_id": uuid_v_7,
        "event_type": "task_event",
        "event_date": "2026-09-01T10:00:00Z",
    }).encode("utf-8")
    changed_body = json.dumps({
        "event_id": uuid_v_7,
        "event_type": "game_event",
        "event_date": "2026-09-01T10:00:00Z",
    }).encode("utf-8")

    service = RabbitService(test_session_factory)
    await service.handle_message(original_body)

    with pytest.raises(PermanentProcessingError, match="event_id_conflict"):
        await service.handle_message(changed_body)

    async with test_session_factory() as session:
        event = await session.get(Event, event_id)
        receipt = await session.get(EventReceipt, event_id)

    assert event is not None
    assert event.event_type == "task_event"
    assert receipt is not None
    assert receipt.payload_hash == calculate_payload_hash(original_body)


@pytest.mark.asyncio
async def test_unknown_event_type_is_not_saved(
        test_session_factory: async_sessionmaker[AsyncSession],
        uuid_v_7: str,
) -> None:
    event_id = UUID(uuid_v_7)
    body = json.dumps({
        "event_id": uuid_v_7,
        "event_type": "unknown_event",
        "event_date": "2026-09-01T10:00:00Z",
    }).encode("utf-8")

    service = RabbitService(test_session_factory)
    await service.handle_message(body)

    async with test_session_factory() as session:
        event = await session.get(Event, event_id)
        receipt = await session.get(EventReceipt, event_id)

    assert event is None
    assert receipt is None
