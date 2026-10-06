import hashlib
import json
import logging
from datetime import timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.events.models import Event, EventReceipt
from src.rabbit.exceptions import PermanentProcessingError, TemporaryProcessingError
from src.rabbit.schemas import EventMessage

logger = logging.getLogger(__name__)


class RabbitService:
    ALLOWED_EVENT_TYPES = [
        "task_event",
        "survey_event",
        "game_event",
    ]

    def __init__(
            self,
            session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def handle_message(self, body: bytes) -> None:
        try:
            event = EventMessage.model_validate_json(body)
        except ValidationError as error:
            raise PermanentProcessingError(
                "Invalid event message",
            ) from error

        if event.event_type not in self.ALLOWED_EVENT_TYPES:
            logger.warning(
                "Неизвестный тип события: %s",
                event.event_type,
            )
            return

        payload_hash = self.calculate_payload_hash(body)
        await self.save_event(event, payload_hash)

    @staticmethod
    def calculate_payload_hash(body: bytes) -> str:
        payload = json.loads(body)
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    async def save_event(
            self,
            event: EventMessage,
            payload_hash: str) -> None:
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    stmt = (
                        insert(EventReceipt)
                        .values(
                            event_id=event.event_id,
                            payload_hash=payload_hash,
                        )
                        .on_conflict_do_nothing(
                            index_elements=[EventReceipt.event_id],
                        )
                        .returning(EventReceipt.event_id)
                    )
                    result = await session.execute(stmt)
                    inserted_event_id = result.scalar_one_or_none()

                    if inserted_event_id is None:
                        existing_hash = await session.scalar(
                            select(EventReceipt.payload_hash).where(
                                EventReceipt.event_id == event.event_id
                            )
                        )

                        if existing_hash != payload_hash:
                            raise PermanentProcessingError(
                                "event_id_conflict"
                            )
                        return
                    session.add(
                        Event(
                            id=event.event_id,
                            event_type=event.event_type,
                            event_date=event.event_date.astimezone(timezone.utc),
                            metadata_=event.metadata,
                            external_user_id=event.external_user_id,
                        )
                    )
        except SQLAlchemyError as error:
            raise TemporaryProcessingError(
                "Cannot save event to database",
            ) from error
