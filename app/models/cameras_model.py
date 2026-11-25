from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.database.base import Base


class UserCamerasTable(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String)
    url: Mapped[str] = mapped_column(String(250), nullable=False)
    user: Mapped["UserTable"] = relationship("UserTable", back_populates="cameras")
    zones: Mapped[list["CamerasZoneTable"]] = relationship(
        "CamerasZoneTable", back_populates="camera", cascade="all, delete-orphan"
    )


class CamerasZoneTable(Base):
    __tablename__ = "cameras_zones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="intrusion", server_default="intrusion"
    )
    color: Mapped[str] = mapped_column(
        String(16), nullable=False, default="indigo", server_default="indigo"
    )
    coordinates: Mapped[list[dict[str, float]]] = mapped_column(JSON, nullable=False)
    object_class_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=lambda: [0, 2, 7], server_default=text("'[0,2,7]'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    camera: Mapped["UserCamerasTable"] = relationship(
        "UserCamerasTable", back_populates="zones"
    )
