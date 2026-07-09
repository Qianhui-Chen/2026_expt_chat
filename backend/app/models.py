from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (UniqueConstraint("user_id", "attempt_number", name="uq_user_attempt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    emotion: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    emotion_label: Mapped[str] = mapped_column(String(16))
    position_label: Mapped[str] = mapped_column(String(16))
    ai_round_count: Mapped[int] = mapped_column(Integer, default=0)
    chat_finished: Mapped[int] = mapped_column(Integer, default=0)
    experiment_finished: Mapped[int] = mapped_column(Integer, default=0)
    has_similar_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completion_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    click_events: Mapped[list["ClickEvent"]] = relationship(back_populates="session")
    page_events: Mapped[list["PageEvent"]] = relationship(back_populates="session")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session")


class ClickEvent(Base):
    __tablename__ = "click_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("user_sessions.id"), index=True)
    page: Mapped[str] = mapped_column(String(64))
    element: Mapped[str] = mapped_column(String(128))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["UserSession"] = relationship(back_populates="click_events")


class PageEvent(Base):
    __tablename__ = "page_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("user_sessions.id"), index=True)
    page: Mapped[str] = mapped_column(String(64))
    entered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dwell_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped["UserSession"] = relationship(back_populates="page_events")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("user_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    round_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["UserSession"] = relationship(back_populates="chat_messages")
