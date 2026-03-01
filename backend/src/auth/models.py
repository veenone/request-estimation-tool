"""SQLAlchemy 2.0 declarative models for authentication and authorization."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database.models import Base


class User(Base):
    """Application user account.

    Supports local password auth, LDAP/AD, and OIDC providers.
    When ``auth_provider`` is not ``'local'``, ``password_hash`` may be
    ``None`` because credential validation is delegated to the external IdP.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_provider: Mapped[str] = mapped_column(String, nullable=False, default="local")
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(
        String, nullable=False, default="VIEWER"
    )  # VIEWER | ESTIMATOR | APPROVER | ADMIN
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    team_member_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("team_members.id", ondelete="SET NULL"), nullable=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class UserSession(Base):
    """Persistent refresh-token session record.

    A new row is inserted each time a refresh token is issued and deleted
    when the token is consumed or the session is explicitly revoked.
    """

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="sessions")


class AuditLog(Base):
    """Immutable audit trail entry.

    Records all significant actions (login, CRUD, report generation, etc.)
    together with the acting user, the affected resource, and the client IP.
    ``details_json`` carries arbitrary extra context as a JSON string.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")
