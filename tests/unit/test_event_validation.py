import uuid
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.rabbit.schemas import EventMessage


def test_rejects_event_id_that_is_not_uuid7():
    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "task_event",
        "event_date": "2026-09-01T10:00:00Z",
    }

    with pytest.raises(ValidationError, match="event_id must be UUIDv7"):
        EventMessage.model_validate(payload)


def test_accepts_valid_event(uuid_v_7: str):
    event_id = UUID(uuid_v_7)

    event = EventMessage.model_validate({
        "event_id": str(event_id),
        "event_type": "task_event",
        "event_date": "2026-09-01T10:00:00Z",
    })

    assert event.event_id == event_id
    assert event.event_date.utcoffset().total_seconds() == 0


def test_rejects_event_without_timezone(uuid_v_7: str):
    event_id = UUID(uuid_v_7)

    payload = {
        "event_id": str(event_id),
        "event_type": "task_event",
        "event_date": "2026-09-01T10:00:00",
    }

    with pytest.raises(ValidationError) as exc_info:
        EventMessage.model_validate(payload)

    assert exc_info.value.errors()[0]["type"] == "timezone_aware"

def test_event_rejected_with_extra_fields(uuid_v_7: str):
    event_id = UUID(uuid_v_7)

    payload = {
        "event_id": str(event_id),
        "event_type": "task_event",
        "event_date": "2026-09-01T10:00:00Z",
        "extra": "some extra field",
    }

    with pytest.raises(ValidationError) as exc_info:
        EventMessage.model_validate(payload)
