import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.dependencies.auth import get_current_user
from app.models.security_event_model import TelegramIntegrationTable
from app.models.user_model import UserTable
from app.schemas.security_schemas import (
    TelegramLinkResponse,
    TelegramNotificationsUpdate,
    TelegramStatusResponse,
)
from app.services.alert_processor import alert_processor
from app.services.telegram_bot import telegram_bot

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.get("/status", response_model=TelegramStatusResponse)
async def telegram_status(
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    integration = await db.scalar(
        select(TelegramIntegrationTable).where(
            TelegramIntegrationTable.user_id == current_user.id
        )
    )
    return TelegramStatusResponse(
        configured=telegram_bot.configured,
        connected=bool(integration and integration.chat_id),
        notifications_enabled=bool(
            integration
            and integration.chat_id
            and integration.notifications_enabled
        ),
        bot_username=await alert_processor.get_bot_username(),
    )


@router.post("/link-code", response_model=TelegramLinkResponse)
async def create_telegram_link_code(
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    if not telegram_bot.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram integration is not configured on the server.",
        )

    username = await alert_processor.get_bot_username()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is temporarily unavailable.",
        )

    code = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    integration = await db.scalar(
        select(TelegramIntegrationTable).where(
            TelegramIntegrationTable.user_id == current_user.id
        )
    )
    if integration is None:
        integration = TelegramIntegrationTable(
            user_id=current_user.id,
            notifications_enabled=False,
        )
        db.add(integration)

    integration.link_code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    integration.link_code_expires_at = expires_at
    await db.commit()
    return TelegramLinkResponse(
        bot_start_url=f"https://t.me/{username}?start={code}",
        expires_at=expires_at,
    )


@router.patch("/notifications", response_model=TelegramStatusResponse)
async def update_telegram_notifications(
    body: TelegramNotificationsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    integration = await db.scalar(
        select(TelegramIntegrationTable).where(
            TelegramIntegrationTable.user_id == current_user.id
        )
    )
    if integration is None or not integration.chat_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connect a Telegram account before enabling notifications.",
        )
    integration.notifications_enabled = body.enabled
    await db.commit()
    return TelegramStatusResponse(
        configured=telegram_bot.configured,
        connected=True,
        notifications_enabled=integration.notifications_enabled,
        bot_username=telegram_bot.username,
    )


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_telegram(
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
) -> None:
    integration = await db.scalar(
        select(TelegramIntegrationTable).where(
            TelegramIntegrationTable.user_id == current_user.id
        )
    )
    if integration is None:
        return
    integration.chat_id = None
    integration.notifications_enabled = False
    integration.link_code_hash = None
    integration.link_code_expires_at = None
    integration.linked_at = None
    await db.commit()
