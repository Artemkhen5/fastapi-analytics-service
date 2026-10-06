import asyncio
import logging

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from src.config import Settings
from src.database import async_session_factory
from src.rabbit.exceptions import PermanentProcessingError, TemporaryProcessingError
from src.rabbit.protocols import MessageHandler
from src.rabbit.service import RabbitService

logger = logging.getLogger(__name__)


class RabbitConsumer:
    MAX_RETRIES = 3
    RETRY_DELAY_MS = 5_000

    def __init__(self, rabbit_url: str, handler: MessageHandler) -> None:
        self.rabbit_url = rabbit_url
        self.handler = handler
        self.connection: aio_pika.abc.AbstractRobustConnection | None = None
        self.channel: aio_pika.abc.AbstractRobustChannel | None = None
        self.queue: aio_pika.abc.AbstractRobustQueue | None = None
        self.dlx: aio_pika.abc.AbstractRobustExchange | None = None
        self.retry_exchange: aio_pika.abc.AbstractRobustExchange | None = None

    async def run(self) -> None:
        await self.connect()

        if self.connection is None:
            raise RuntimeError("RABBITMQ_URL not set")

        async with self.connection as conn:
            self.channel = await conn.channel(
                publisher_confirms=True,
                on_return_raises=True,
            )

            await self.channel.set_qos(prefetch_count=1)
            await self.setup_topology()
            await self.consume()

    async def connect(self) -> None:
        self.connection = await aio_pika.connect_robust(
            self.rabbit_url
        )

    async def setup_topology(self) -> None:
        if self.channel is None:
            raise RuntimeError("RabbitMQ channel is not initialized")

        self.dlx = await self.channel.declare_exchange(
            "analytics.dlx",
            aio_pika.ExchangeType.DIRECT,
            durable=True
        )
        dlq = await self.channel.declare_queue(
            "analytics.dlq",
            durable=True,
        )
        await dlq.bind(
            self.dlx,
            routing_key="analytics.dlq",
        )

        exchange = await self.channel.declare_exchange(
            "events",
            aio_pika.ExchangeType.FANOUT,
            durable=True,
        )
        self.queue = await self.channel.declare_queue(
            "analytics.events",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "analytics.dlx",
                "x-dead-letter-routing-key": "analytics.dlq",
            }
        )
        await self.queue.bind(exchange)

        self.retry_exchange = await self.channel.declare_exchange(
            "analytics.retry.exchange",
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )
        retry_queue = await self.channel.declare_queue(
            "analytics.retry",
            durable=True,
            arguments={
                "x-message-ttl": self.RETRY_DELAY_MS,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": "analytics.events",
            }
        )
        await retry_queue.bind(
            self.retry_exchange,
            routing_key="analytics.retry",
        )

    async def consume(self) -> None:
        if self.queue is None:
            raise RuntimeError("RabbitMQ queue is not initialized")

        async with self.queue.iterator() as queue_iter:
            async for message in queue_iter:
                try:
                    await self.handler.handle_message(message.body)
                except TemporaryProcessingError:
                    headers = message.headers or {}
                    retry_count = int(headers.get("x-retry-count", 0))

                    if retry_count >= self.MAX_RETRIES:
                        logger.exception("Retry limit reached")
                        await message.reject(requeue=False)
                    else:
                        try:
                            await self.send_to_retry(
                                message=message,
                                retry_count=retry_count + 1
                            )
                        except Exception:
                            logger.exception("Cannot publish message to retry queue")
                            raise
                        else:
                            await message.ack()
                except PermanentProcessingError:
                    logger.exception("Permanent message processing error")
                    await message.reject(requeue=False)
                except Exception:
                    logger.exception("Unexpected RabbitMQ consume exception")
                    await message.reject(requeue=False)
                else:
                    await message.ack()

    async def send_to_retry(
            self,
            message: AbstractIncomingMessage,
            retry_count: int,
    ) -> None:
        if self.retry_exchange is None:
            raise RuntimeError("RabbitMQ exchange is not initialized")

        headers = dict(message.headers or {})
        headers["x-retry-count"] = retry_count

        retry_message = aio_pika.Message(
            body=message.body,
            headers=headers,
            content_type=message.content_type or "application/json",
            message_id=message.message_id,
            correlation_id=message.correlation_id,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self.retry_exchange.publish(
            retry_message,
            routing_key="analytics.retry",
            mandatory=True,
        )
        logger.info(
            "Message published to retry queue: message_id=%s, retry_count=%s, delay_ms=%s",
            message.message_id,
            retry_count,
            self.RETRY_DELAY_MS, )


async def main() -> None:
    settings = Settings()
    service = RabbitService(session_factory=async_session_factory)
    consumer = RabbitConsumer(
        rabbit_url=settings.RABBITMQ_URL,
        handler=service
    )

    await consumer.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
