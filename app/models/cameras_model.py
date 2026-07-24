from sqlalchemy import Integer, String, ForeignKey, Column
from sqlalchemy.orm import Mapped, mapped_column,relationship


from app.database.base import Base

class UserCamerasTable(Base):
    __tablename__ = "cameras"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String)
    url: Mapped[str] = mapped_column(String(250), nullable=False)
    user: Mapped["UserTable"] = relationship("UserTable", back_populates="cameras")


