from datetime import datetime

from pydantic import BaseModel


class DetectionEventResponse(BaseModel):
    id: int
    camera_id: int
    camera_name: str
    zone_id: int | None
    zone_name: str | None
    object_class_id: int
    confidence: float
    bounding_box: dict[str, float]
    occurred_at: datetime
    notification_status: str
    snapshot_url: str


class TelegramStatusResponse(BaseModel):
    configured: bool
    connected: bool
    notifications_enabled: bool
    bot_username: str | None


class TelegramLinkResponse(BaseModel):
    bot_start_url: str
    expires_at: datetime


class TelegramNotificationsUpdate(BaseModel):
    enabled: bool
