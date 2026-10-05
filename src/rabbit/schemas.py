from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator, AwareDatetime


class EventMessage(BaseModel):
    event_id: UUID
    event_type: str = Field(min_length=1)
    event_date: AwareDatetime
    external_user_id: str | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, value: UUID) -> UUID:
        if value.version != 7:
            raise ValueError("event_id must be UUIDv7")
        return value
