"""Workspaces and membership with role-based access."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow
from app.models.base import TimestampMixin, UuidPkMixin


class Workspace(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))

    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    cases = relationship("Case", back_populates="workspace", cascade="all, delete-orphan")


class WorkspaceMember(Base, UuidPkMixin):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),)

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    joined_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)

    user = relationship("User", back_populates="memberships")
    workspace = relationship("Workspace", back_populates="members")
