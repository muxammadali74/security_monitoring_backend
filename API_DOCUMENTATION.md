# Документация backend-сервиса мониторинга

Документ описывает API и основные компоненты проекта по текущему коду приложения.

## О проекте

Backend предоставляет API для регистрации и авторизации пользователей, добавления RTSP-камер, просмотра кадров и управления видеопотоками. Для HTTP API используется FastAPI; данные хранятся через SQLAlchemy в PostgreSQL, авторизация работает на JWT. Обработка видеопотока и детекций находится в `app/services/stream/`.

Основные каталоги:

| Путь | Назначение |
|---|---|
| `app/routers/` | HTTP- и WebSocket-маршруты |
| `app/schemas/` | Pydantic-схемы запросов и ответов |
| `app/models/` | Модели базы данных |
| `app/services/stream/` | Работа с видеопотоком и детекциями |
| `app/dependencies/` | Зависимости FastAPI, включая проверку JWT |
| `app/database/` | Подключение и инициализация базы данных |

## Базовые адреса

- Префикс API по умолчанию: `/api/v1` (настраивается через `API_V1_STR`).
- Проверка состояния сервиса: `GET /health` — находится вне префикса API.
- Swagger UI FastAPI по умолчанию: `/docs`; схема OpenAPI: `/openapi.json`.

В таблице ниже пути приведены с префиксом `/api/v1`, если не указано иное.

## Таблица маршрутов

| Метод | Путь | Авторизация | Назначение | Параметры / тело запроса | Ответ |
|---|---|---|---|---|---|
| POST | `/api/v1/registration` | Не требуется | Регистрация пользователя | JSON: `name`, `email`, `password`, `repeat_password` | `201`; данные пользователя: `id`, `name`, `email` |
| POST | `/api/v1/registration/admin?secret_key=...` | Секретный ключ в query-параметре | Регистрация администратора | JSON как при обычной регистрации; query-параметр `secret_key` | `201`; данные пользователя: `id`, `name`, `email` |
| POST | `/api/v1/login` | Не требуется | Вход и получение JWT | Форма `application/x-www-form-urlencoded`: `username` (email) и `password` | `access_token`, `token_type` |
| GET | `/api/v1/newstream/` | Bearer JWT | Список камер текущего пользователя | Нет | Массив камер: `id`, `user_id`, `name`, `url` |
| POST | `/api/v1/newstream/` | Bearer JWT | Добавление камеры текущему пользователю | JSON: `name`, `url` | `id`, `user_id`, `name`, `url` |
| DELETE | `/api/v1/newstream/{camera_id}` | Bearer JWT; только владелец камеры | Удаление камеры и связанных зон; активный поток останавливается | Path-параметр `camera_id` | `204`; пустое тело |
| POST | `/api/v1/newstream/preview` | Bearer JWT | Получение одного кадра с RTSP-источника без сохранения камеры | JSON: `rtsp_url` | `image_base64`, `width`, `height` |
| GET | `/api/v1/stream/{camera_id}/zones` | Bearer JWT; владелец камеры | Получение зон камеры | Path-параметр `camera_id` | Массив зон |
| POST | `/api/v1/stream/{camera_id}/zones` | Bearer JWT; владелец камеры | Создание зоны камеры | JSON: `camera_id`, `name`, `zone_type`, `color`, `coordinates`, `object_class_ids`, `is_active` | `201`; данные зоны |
| PATCH | `/api/v1/stream/zones/{zone_id}` | Bearer JWT; владелец камеры | Обновление зоны | JSON с изменяемыми полями зоны | Данные зоны |
| DELETE | `/api/v1/stream/zones/{zone_id}` | Bearer JWT; владелец камеры | Удаление зоны | Path-параметр `zone_id` | `204`; пустое тело |
| POST | `/api/v1/stream/{camera_id}/start` | Bearer JWT; только владелец камеры | Запуск видеопотока камеры | Path-параметр `camera_id` | `status`, `message` |
| POST | `/api/v1/stream/{camera_id}/stop` | Bearer JWT; только владелец камеры | Остановка видеопотока камеры | Path-параметр `camera_id` | `status`, `message` |
| GET | `/api/v1/stream/active-streams` | Bearer JWT | Получение активных потоков текущего пользователя | Нет | `active_camera_ids`, `total_active` |
| WS | `/api/v1/stream/{camera_id}/ws?token=...` | JWT в query-параметре `token`; только владелец камеры | Получение кадров и метаданных активного потока | Path-параметр `camera_id`, query-параметр `token` | JSON-сообщение с `frame_id` и `detections`, затем байты кадра |
| GET | `/api/v1/events/?camera_id=...&limit=100` | Bearer JWT | История событий входа в зоны | Необязательные фильтры `camera_id`, `limit` (1–500) | Массив событий |
| GET | `/api/v1/events/{event_id}/snapshot` | Bearer JWT; владелец события | JPEG-снимок события | Path-параметр `event_id` | `image/jpeg` |
| GET | `/api/v1/telegram/status` | Bearer JWT | Состояние Telegram-связи и уведомлений | Нет | `configured`, `connected`, `notifications_enabled`, `bot_username` |
| POST | `/api/v1/telegram/link-code` | Bearer JWT | Создание одноразовой ссылки связи Telegram | Нет | `bot_start_url`, `expires_at` |
| PATCH | `/api/v1/telegram/notifications` | Bearer JWT | Включение/выключение уведомлений | JSON: `{"enabled": true}` | Состояние Telegram |
| DELETE | `/api/v1/telegram/connection` | Bearer JWT | Отключение Telegram-аккаунта | Нет | `204`; пустое тело |
| GET | `/api/v1/dashboard/statistics` | Не требуется | Статистика dashboard (пока заглушка) | Нет | `active_streams`, `total_streams`, `events_today` |
| GET | `/health` | Не требуется | Проверка состояния сервиса | Нет | `{"status": "ok"}` |

Все маршруты камер, зон, событий и Telegram проверяют Bearer JWT и ограничивают
данные владельцем. WebSocket проверяет JWT из query-параметра.
`/dashboard/statistics` пока возвращает нулевые значения для `total_streams` и
`events_today`, поэтому frontend не использует эти поля как реальные показатели.

## Форматы запросов

### Регистрация

```json
{
  "name": "Имя пользователя",
  "email": "user@example.com",
  "password": "пароль",
  "repeat_password": "пароль"
}
```

Пароль и его повтор должны совпадать. Для регистрации администратора передайте `secret_key` как query-параметр.

### Добавление камеры

```json
{
  "name": "Вход",
  "url": "rtsp://camera.example/stream"
}
```

### Создание зоны

```json
{
  "camera_id": 1,
  "name": "Зона входа",
  "zone_type": "intrusion",
  "color": "indigo",
  "coordinates": [
    {"x": 0.1, "y": 0.1},
    {"x": 0.9, "y": 0.1},
    {"x": 0.5, "y": 0.9}
  ],
  "object_class_ids": [0, 2, 7],
  "is_active": true
}
```

Координаты нормализованы в диапазоне от `0.0` до `1.0`; требуется не менее
трёх уникальных точек, образующих непересекающийся полигон с ненулевой площадью.
Поддерживаются классы COCO: `0` (person), `2` (car), `7` (truck). Событие
создаётся при входе объекта в активную зону; снимок хранится в базе данных.

## Миграции и Telegram

После запуска приложения для инициализации ещё не созданных таблиц выполните
миграции из каталога backend:

```powershell
alembic upgrade head
```

Для Telegram задайте `TELEGRAM_BOT_TOKEN` в серверном `.env` и перезапустите
backend. Без токена API статуса сообщает `configured: false`; создание ссылки
возвращает `503`. Секрет бота не передаётся во frontend.

## Авторизация

Для маршрутов, требующих HTTP-аутентификацию, передавайте полученный токен в заголовке:

```text
Authorization: Bearer <access_token>
```

Токен выдаётся при входе и содержит срок действия. Для WebSocket токен передаётся параметром `token` в URL.

