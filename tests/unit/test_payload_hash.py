import json

from src.rabbit.payload import calculate_payload_hash


def test_payload_hash() -> None:
    payload = {
        "event_type": "game_event",
        "event_date": "2026-09-01T10:00:00Z",
        "event_id": "01994f3c-8a00-7a1b-8c2d-3e4f50617283"
    }

    reordered_payload = {
        "event_id": "01994f3c-8a00-7a1b-8c2d-3e4f50617283",
        "event_date": "2026-09-01T10:00:00Z",
        "event_type": "game_event"
    }

    assert calculate_payload_hash(json.dumps(payload).encode()) == calculate_payload_hash(
        json.dumps(reordered_payload).encode())
