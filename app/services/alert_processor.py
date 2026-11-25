import asyncio
import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database.connection import async_session
from app.models.cameras_model import CamerasZoneTable, UserCamerasTable
from app.models.security_event_model import (
    DetectionEventTable,
    TelegramIntegrationTable,
)
from app.services.telegram_bot import TelegramApiError, telegram_bot

logger = logging.getLogger(__name__)


class AlertProcessor:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._events: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)
        self._notifications: asyncio.Queue[int] = asyncio.Queue(maxsize=128)
        self._tasks: list[asyncio.Task] = []
        self._poll_offset: int | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._tasks = [
            asyncio.create_task(self._persist_events(), name="security-event-writer"),
            asyncio.create_task(
                self._send_notifications(), name="telegram-alert-sender"
            ),
        ]
        if telegram_bot.configured:
            self._tasks.append(
                asyncio.create_task(self._poll_telegram(), name="telegram-updates")
            )

    async def stop(self) -> None:
        poll_tasks = [task for task in self._tasks if task.get_name() == "telegram-updates"]
        for task in poll_tasks:
            task.cancel()
        if poll_tasks:
            await asyncio.gather(*poll_tasks, return_exceptions=True)

        try:
            await asyncio.wait_for(self._events.join(), timeout=10)
            await asyncio.wait_for(self._notifications.join(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Timed out draining alert queues during shutdown.")

        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._loop = None

    def submit_from_worker(self, event: dict) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            logger.error("Dropped a camera alert because the alert processor is stopped.")
            return
        loop.call_soon_threadsafe(self._enqueue_event, event)

    def _enqueue_event(self, event: dict) -> None:
        try:
            self._events.put_nowait(event)
        except asyncio.QueueFull:
            logger.error(
                "Dropped a camera alert because the event queue is full (camera_id=%s).",
                event.get("camera_id"),
            )

    async def get_bot_username(self) -> str | None:
        if not telegram_bot.configured:
            return None
        if telegram_bot.username:
            return telegram_bot.username
        try:
            await asyncio.to_thread(telegram_bot.get_me)
        except TelegramApiError:
            logger.warning("Could not verify the configured Telegram bot.")
            return None
        return telegram_bot.username

    async def _persist_events(self) -> None:
        while True:
            payload = await self._events.get()
            try:
                await self._persist_event(payload)
            except Exception:
                logger.exception(
                    "Could not persist a camera alert (camera_id=%s).",
                    payload.get("camera_id"),
                )
            finally:
                self._events.task_done()

    async def _persist_event(self, payload: dict) -> None:
        notification_event_id: int | None = None
        async with async_session() as db:
            event = DetectionEventTable(
                user_id=payload["user_id"],
                camera_id=payload["camera_id"],
                zone_id=payload["zone_id"],
                object_class_id=payload["object_class_id"],
                confidence=payload["confidence"],
                bounding_box=payload["bounding_box"],
                occurred_at=payload["occurred_at"],
                snapshot=payload["snapshot"],
                notification_status="disabled",
            )
            db.add(event)
            await db.flush()
            integration = await db.scalar(
                select(TelegramIntegrationTable).where(
                    TelegramIntegrationTable.user_id == payload["user_id"]
                )
            )

            if (
                telegram_bot.configured
                and integration is not None
                and integration.chat_id
                and integration.notifications_enabled
            ):
                event.notification_status = "pending"
                notification_event_id = event.id

            await db.commit()
        if notification_event_id is not None:
            try:
                self._notifications.put_nowait(notification_event_id)
            except asyncio.QueueFull:
                async with async_session() as db:
                    event = await db.get(DetectionEventTable, notification_event_id)
                    if event is not None:
                        event.notification_status = "failed"
                        event.notification_error = "Telegram notification queue is full."
                        await db.commit()

    async def _send_notifications(self) -> None:
        while True:
            event_id = await self._notifications.get()
            try:
                await self._send_event_notification(event_id)
            except Exception:
                logger.exception("Could not process Telegram alert for event_id=%s.", event_id)
            finally:
                self._notifications.task_done()

    async def _send_event_notification(self, event_id: int) -> None:
        async with async_session() as db:
            event = await db.get(DetectionEventTable, event_id)
            if event is None:
                return
            integration = await db.scalar(
                select(TelegramIntegrationTable).where(
                    TelegramIntegrationTable.user_id == event.user_id
                )
            )
            camera = await db.get(UserCamerasTable, event.camera_id)
            zone = (
                await db.get(CamerasZoneTable, event.zone_id)
                if event.zone_id is not None
                else None
            )
            if (
                integration is None
                or not integration.chat_id
                or not integration.notifications_enabled
            ):
                event.notification_status = "disabled"
                event.notification_error = None
                await db.commit()
                return

            chat_id = integration.chat_id
            snapshot = event.snapshot
            class_name = {0: "Person", 2: "Car", 7: "Truck"}.get(
                event.object_class_id, f"Class {event.object_class_id}"
            )
            caption = (
                "VISION AI ALERT\n"
                f"Camera: {camera.name if camera else event.camera_id}\n"
                f"Zone: {zone.name if zone else 'Deleted zone'}\n"
                f"Object: {class_name}\n"
                f"Confidence: {event.confidence:.0%}\n"
                f"Time: {event.occurred_at.astimezone(timezone.utc).strftime('%H:%M:%S UTC')}\n"
                "Object detected inside a security zone."
            )

        last_error: str | None = None
        for attempt in range(3):
            try:
                await asyncio.to_thread(
                    telegram_bot.send_photo, chat_id, snapshot, caption
                )
                last_error = None
                break
            except TelegramApiError:
                last_error = "Telegram API request failed."
                if attempt < 2:
                    await asyncio.sleep(2**attempt)

        async with async_session() as db:
            event = await db.get(DetectionEventTable, event_id)
            if event is None:
                return
            event.notification_status = "sent" if last_error is None else "failed"
            event.notification_error = last_error
            await db.commit()

    async def _poll_telegram(self) -> None:
        await self.get_bot_username()
        while True:
            try:
                updates = await asyncio.to_thread(
                    telegram_bot.get_updates, self._poll_offset
                )
                for update in updates:
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        self._poll_offset = update_id + 1
                    await self._handle_telegram_update(update)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Telegram update polling failed; retrying shortly.")
                await asyncio.sleep(5)

    async def _handle_telegram_update(self, update: dict) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return
        chat = message.get("chat")
        text = message.get("text")
        if not isinstance(chat, dict) or not isinstance(chat.get("id"), int):
            return
        if not isinstance(text, str) or not text.startswith("/start"):
            return

        chat_id = str(chat["id"])
        parts = text.split(maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            await asyncio.to_thread(
                telegram_bot.send_message,
                chat_id,
                "To connect, open the secure link generated in your Vision AI settings.",
            )
            return

        code_hash = hashlib.sha256(parts[1].strip().encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        reply = "This link code is invalid or expired. Generate a new link in Vision AI."

        async with async_session() as db:
            integration = await db.scalar(
                select(TelegramIntegrationTable).where(
                    TelegramIntegrationTable.link_code_hash == code_hash,
                    TelegramIntegrationTable.link_code_expires_at > now,
                )
            )
            if integration is not None:
                existing = await db.scalar(
                    select(TelegramIntegrationTable).where(
                        TelegramIntegrationTable.chat_id == chat_id,
                        TelegramIntegrationTable.id != integration.id,
                    )
                )
                if existing is not None:
                    reply = "This Telegram account is already connected to another Vision AI account."
                else:
                    integration.chat_id = chat_id
                    integration.notifications_enabled = False
                    integration.link_code_hash = None
                    integration.link_code_expires_at = None
                    integration.linked_at = now
                    try:
                        await db.commit()
                        reply = "Telegram is connected. Enable alerts in your Vision AI settings."
                    except IntegrityError:
                        await db.rollback()
                        reply = "This Telegram account is already connected to another Vision AI account."

        await asyncio.to_thread(telegram_bot.send_message, chat_id, reply)


alert_processor = AlertProcessor()
