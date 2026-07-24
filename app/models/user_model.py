from sqlalchemy import Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base



class UserTable(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    cameras: Mapped[list["UserCamerasTable"]] = relationship(
        "UserCamerasTable", 
        back_populates="user",
        cascade="all, delete-orphan" 
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
