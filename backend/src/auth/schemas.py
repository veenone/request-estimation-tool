"""Pydantic v2 schemas for the authentication module.

These schemas are used for request validation and response serialization
by the FastAPI auth routes.  They are intentionally kept separate from the
SQLAlchemy models so that the API surface can evolve independently of the
database layer.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Credentials submitted by the client at login time."""

    username: str
    password: str


class RefreshRequest(BaseModel):
    """Opaque refresh token sent to obtain a new token pair."""

    refresh_token: str


class UserCreate(BaseModel):
    """Payload for creating a new user account."""

    username: str
    email: Optional[str] = None
    display_name: str
    password: Optional[str] = None
    role: str = "VIEWER"
    auth_provider: str = "local"
    team_member_id: Optional[int] = None


class UserUpdate(BaseModel):
    """Partial payload for updating an existing user account.

    All fields are optional — only supplied fields are applied.
    """

    email: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    team_member_id: Optional[int] = None


class PasswordChange(BaseModel):
    """Payload for a self-service password change request."""

    current_password: str
    new_password: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UserOut(BaseModel):
    """Public representation of a user account returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    display_name: str
    role: str
    auth_provider: str
    is_active: bool
    team_member_id: Optional[int] = None
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    """Token pair returned after a successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class AuditLogOut(BaseModel):
    """Public representation of a single audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    details_json: str = "{}"
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None
