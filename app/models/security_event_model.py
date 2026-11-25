from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DetectionEventTable(Base):
    __tablename__ = "detection_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras_zones.id", ondelete="SET NULL"), nullable=True, index=True
    )
    object_class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bounding_box: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    snapshot: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    notification_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    notification_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class TelegramIntegrationTable(Base):
    __tablename__ = "telegram_integrations"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_telegram_integrations_user_id"),
        UniqueConstraint("chat_id", name="uq_telegram_integrations_chat_id"),
        UniqueConstraint("link_code_hash", name="uq_telegram_integrations_link_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    link_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    link_code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    linked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

