from typing import Protocol


class MessageHandler(Protocol):
    async def handle_message(self, body: bytes) -> None:
        pass
