# Fast API Analytics

Сервис приёма аналитических событий на FastAPI, RabbitMQ и PostgreSQL. **Статус: в разработке.** Проект используется для отработки асинхронной обработки сообщений, миграций и идемпотентного сохранения.

## Что есть сейчас

- Отдельный RabbitMQ worker с durable-очередями, повторными попытками при временных ошибках и dead-letter queue (DLQ).
- Валидация входных событий через Pydantic, включая проверку UUIDv7 и даты с часовым поясом.
- Миграции Alembic для таблиц `events` и `event_receipts`.
- Сохранение события и квитанции в одной транзакции. Повтор с тем же `event_id` и содержимым пропускается; повтор с другим содержимым считается конфликтом.

HTTP-приложение пока содержит только демонстрационные маршруты. Аналитический API, редактирование и удаление событий, а также автоматические тесты ещё не реализованы.

## Стек

Python 3.12, FastAPI, Pydantic, SQLAlchemy Async, asyncpg, Alembic, aio-pika, PostgreSQL, RabbitMQ, Docker Compose.

## Локальный запуск

Нужны Docker Compose и уже запущенный RabbitMQ, доступный worker в Docker-сети `shared_rabbit`. Эта сеть в `compose.yaml` объявлена внешней. Адрес RabbitMQ указывается в `.env`; имя хоста в URL должно разрешаться **из контейнера**, а не только с хоста.

1. Скопируйте `.env.example` в `.env` и укажите свои параметры RabbitMQ и PostgreSQL. `.env` содержит локальные настройки и не должен попадать в Git.
2. Если сеть `shared_rabbit` ещё не создана, создайте её и подключите к ней контейнер RabbitMQ:

   ```bash
   docker network create shared_rabbit
   docker network connect shared_rabbit <rabbitmq-container>
   ```

   Если сеть или подключение уже существуют, повторять эти команды не нужно.

3. Запустите зависимости, примените миграции, затем запустите приложение и worker:

   ```bash
   docker compose up -d postgres redis
   docker compose run --rm app alembic upgrade head
   docker compose up -d --build app worker
   ```

4. Проверьте логи worker:

   ```bash
   docker compose logs -f worker
   ```

FastAPI будет доступен по адресу `http://localhost:8000`, документация — `http://localhost:8000/docs`. Пока эти HTTP-маршруты не предоставляют аналитику.

## Формат события

Продюсер публикует JSON в fanout exchange `events`. Worker читает очередь `analytics.events`. Сейчас обрабатываются типы `task_event`, `survey_event` и `game_event`; остальные типы подтверждаются без сохранения.

```json
{
  "event_id": "01994f3c-8a00-7a1b-8c2d-3e4f50617283",
  "event_type": "task_event",
  "event_date": "2026-09-01T10:00:00Z",
  "external_user_id": "user-42",
  "metadata": {
    "task_id": 123
  }
}
```

`event_id` должен быть UUIDv7, `event_date` — датой с часовым поясом.
