"""Core authentication and authorization service.

``AuthService`` is the single entry point for all auth operations:
password hashing, JWT issuance/validation, login/refresh/logout flows,
user CRUD, role-based permission checks, and the audit trail.

All methods accept a ``Session`` dependency injected at construction time,
so the service is straightforwardly testable by passing a test-scoped session.

Example usage::

    with SessionLocal() as db:
        svc = AuthService(db)
        result = svc.login("alice", "s3cr3t")
        if result:
            user, access_token, refresh_token = result
"""

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from sqlalchemy.orm import Session

from ..database.models import Configuration
from .models import AuditLog, User, UserSession

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30
DEFAULT_JWT_SECRET = "change-me-in-production-please"

# Role hierarchy used for permission checks.
# A user with a higher numeric value satisfies requirements for all lower roles.
ROLE_HIERARCHY: dict[str, int] = {
    "VIEWER": 0,
    "ESTIMATOR": 1,
    "APPROVER": 2,
    "ADMIN": 3,
}


class AuthService:
    """Stateful auth service bound to a single SQLAlchemy ``Session``.

    The instance caches the resolved JWT secret for the lifetime of the
    session to avoid repeated database round-trips.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self._jwt_secret: Optional[str] = None

    # ------------------------------------------------------------------
    # JWT secret management
    # ------------------------------------------------------------------

    @property
    def jwt_secret(self) -> str:
        """Return the JWT signing secret, generating and persisting it on first use."""
        if self._jwt_secret is None:
            cfg = (
                self.session.query(Configuration)
                .filter(Configuration.key == "jwt_secret")
                .first()
            )
            if cfg and cfg.value:
                self._jwt_secret = cfg.value
            else:
                # Auto-generate a strong secret and store it so all instances
                # share the same key across restarts.
                secret = secrets.token_hex(32)
                if cfg:
                    cfg.value = secret
                else:
                    self.session.add(
                        Configuration(
                            key="jwt_secret",
                            value=secret,
                            description="JWT signing secret (auto-generated)",
                        )
                    )
                self.session.commit()
                self._jwt_secret = secret
        return self._jwt_secret

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """Return a bcrypt hash of *password*.

        Args:
            password: Plaintext password to hash.

        Returns:
            UTF-8 decoded bcrypt hash string suitable for database storage.
        """
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Return ``True`` if *password* matches *password_hash*.

        Args:
            password: Plaintext candidate password.
            password_hash: Stored bcrypt hash to check against.

        Returns:
            ``True`` when the password is correct, ``False`` otherwise.
        """
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    # ------------------------------------------------------------------
    # Token creation
    # ------------------------------------------------------------------

    def create_access_token(self, user: User) -> str:
        """Issue a short-lived signed JWT access token for *user*.

        The token embeds the user id, username, and role so that the
        ``get_current_user`` dependency can reconstruct the user context
        without a database round-trip on every request.

        Args:
            user: Authenticated ``User`` ORM instance.

        Returns:
            Compact JWT string.
        """
        now = datetime.now(timezone.utc)
        payload: dict[str, object] = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": now,
            "type": "access",
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=JWT_ALGORITHM)

    def create_refresh_token(self, user: User) -> str:
        """Issue a long-lived opaque refresh token for *user*.

        A ``UserSession`` row is inserted so the token can be revoked
        server-side.  The token itself is a URL-safe random string and
        contains no user data.

        Args:
            user: Authenticated ``User`` ORM instance.

        Returns:
            Opaque refresh token string.
        """
        token = secrets.token_urlsafe(64)
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        session_record = UserSession(
            user_id=user.id,
            refresh_token=token,
            expires_at=expires_at,
        )
        self.session.add(session_record)
        self.session.commit()
        return token

    # ------------------------------------------------------------------
    # Token validation
    # ------------------------------------------------------------------

    def validate_access_token(self, token: str) -> Optional[dict[str, object]]:
        """Decode and validate a JWT access token.

        Returns the decoded payload dict when the token is valid and has
        ``type == "access"``.  Returns ``None`` for any invalid, expired, or
        malformed token so callers never need to handle JWT-specific exceptions.

        Args:
            token: Compact JWT string from the ``Authorization`` header.

        Returns:
            Decoded payload mapping, or ``None`` if the token is invalid.
        """
        try:
            payload: dict[str, object] = jwt.decode(
                token, self.jwt_secret, algorithms=[JWT_ALGORITHM]
            )
            if payload.get("type") != "access":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    # ------------------------------------------------------------------
    # Auth flows
    # ------------------------------------------------------------------

    def login(
        self, username: str, password: str
    ) -> Optional[tuple[User, str, str]]:
        """Authenticate a local user by username and password.

        Updates ``last_login_at``, issues a new token pair, and writes a
        LOGIN audit event.

        Args:
            username: The account username.
            password: Plaintext password to verify.

        Returns:
            ``(user, access_token, refresh_token)`` on success, ``None`` on
            failure (bad credentials or inactive account).
        """
        user = (
            self.session.query(User)
            .filter(User.username == username, User.is_active == True)  # noqa: E712
            .first()
        )
        if not user or not user.password_hash:
            return None
        if not self.verify_password(password, user.password_hash):
            return None

        user.last_login_at = datetime.now(timezone.utc)
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)
        self.session.commit()

        self.log_action(user.id, "LOGIN")
        return user, access_token, refresh_token

    def refresh(
        self, refresh_token: str
    ) -> Optional[tuple[User, str, str]]:
        """Rotate a refresh token and return a new token pair.

        The old ``UserSession`` row is deleted and a new one is created
        (token rotation).  Returns ``None`` if the token does not exist,
        is expired, or the associated user is inactive.

        Args:
            refresh_token: Opaque refresh token string from the client.

        Returns:
            ``(user, new_access_token, new_refresh_token)`` on success,
            ``None`` otherwise.
        """
        session_record = (
            self.session.query(UserSession)
            .filter(UserSession.refresh_token == refresh_token)
            .first()
        )
        if not session_record:
            return None

        # Ensure the stored datetime is timezone-aware for comparison.
        expires_at = session_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < datetime.now(timezone.utc):
            self.session.delete(session_record)
            self.session.commit()
            return None

        user = self.session.get(User, session_record.user_id)
        if not user or not user.is_active:
            return None

        # Rotate: delete old session, issue new tokens.
        self.session.delete(session_record)
        new_access = self.create_access_token(user)
        new_refresh = self.create_refresh_token(user)
        return user, new_access, new_refresh

    def logout(self, refresh_token: str) -> bool:
        """Revoke a refresh token, invalidating the session server-side.

        Args:
            refresh_token: The opaque refresh token to revoke.

        Returns:
            ``True`` if a session was found and deleted, ``False`` otherwise.
        """
        session_record = (
            self.session.query(UserSession)
            .filter(UserSession.refresh_token == refresh_token)
            .first()
        )
        if session_record:
            self.session.delete(session_record)
            self.session.commit()
            return True
        return False

    # ------------------------------------------------------------------
    # User CRUD
    # ------------------------------------------------------------------

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Fetch a user by primary key.

        Args:
            user_id: Database primary key of the user.

        Returns:
            ``User`` instance or ``None`` when not found.
        """
        return self.session.get(User, user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Fetch a user by their unique username.

        Args:
            username: The username to look up.

        Returns:
            ``User`` instance or ``None`` when not found.
        """
        return (
            self.session.query(User).filter(User.username == username).first()
        )

    def create_user(
        self,
        username: str,
        display_name: str,
        password: Optional[str] = None,
        email: Optional[str] = None,
        role: str = "VIEWER",
        auth_provider: str = "local",
        external_id: Optional[str] = None,
        team_member_id: Optional[int] = None,
    ) -> User:
        """Persist a new user account and return the refreshed instance.

        Args:
            username: Unique login identifier.
            display_name: Human-readable full name.
            password: Plaintext password (hashed before storage).  Pass
                ``None`` for external IdP accounts.
            email: Optional unique email address.
            role: One of ``VIEWER``, ``ESTIMATOR``, ``APPROVER``, ``ADMIN``.
            auth_provider: ``'local'``, ``'ldap'``, or ``'oidc'``.
            external_id: DN or subject identifier from the external IdP.
            team_member_id: FK link to a ``team_members`` row.

        Returns:
            The newly created ``User`` ORM instance with its ``id`` populated.
        """
        password_hash = self.hash_password(password) if password else None
        user = User(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            auth_provider=auth_provider,
            external_id=external_id,
            role=role,
            team_member_id=team_member_id,
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def update_user(self, user_id: int, **kwargs: object) -> Optional[User]:
        """Apply a partial update to a user account.

        Accepts the same field names as ``User`` columns.  Passing
        ``password=<str>`` hashes the value before storing it.  The ``id``
        field is never modified.

        Args:
            user_id: Primary key of the user to update.
            **kwargs: Column name / new value pairs.

        Returns:
            The updated ``User`` instance, or ``None`` when not found.
        """
        user = self.session.get(User, user_id)
        if not user:
            return None
        for key, value in kwargs.items():
            if key == "password" and value:
                user.password_hash = self.hash_password(str(value))
            elif hasattr(user, key) and key != "id":
                setattr(user, key, value)
        self.session.commit()
        self.session.refresh(user)
        return user

    def change_password(
        self, user_id: int, current_password: str, new_password: str
    ) -> bool:
        """Perform a self-service password change after verifying the current one.

        Args:
            user_id: Primary key of the user requesting the change.
            current_password: The user's existing plaintext password.
            new_password: The desired new plaintext password.

        Returns:
            ``True`` on success, ``False`` when the user is not found,
            has no local password, or when ``current_password`` is wrong.
        """
        user = self.session.get(User, user_id)
        if not user or not user.password_hash:
            return False
        if not self.verify_password(current_password, user.password_hash):
            return False
        user.password_hash = self.hash_password(new_password)
        self.session.commit()
        return True

    def delete_user(self, user_id: int) -> bool:
        """Permanently delete a user account.

        Args:
            user_id: Primary key of the user to delete.

        Returns:
            ``True`` when deleted, ``False`` when not found.
        """
        user = self.session.get(User, user_id)
        if not user:
            return False
        self.session.delete(user)
        self.session.commit()
        return True

    def list_users(self, active_only: bool = False) -> list[User]:
        """Return all users ordered alphabetically by username.

        Args:
            active_only: When ``True``, only active accounts are returned.

        Returns:
            List of ``User`` ORM instances.
        """
        q = self.session.query(User)
        if active_only:
            q = q.filter(User.is_active == True)  # noqa: E712
        return q.order_by(User.username).all()

    # ------------------------------------------------------------------
    # Permission checks
    # ------------------------------------------------------------------

    @staticmethod
    def has_permission(user_role: str, required_role: str) -> bool:
        """Return ``True`` when *user_role* satisfies *required_role*.

        Uses the ``ROLE_HIERARCHY`` mapping: a role with a higher numeric
        value satisfies requirements for all lower roles.

        Args:
            user_role: The role assigned to the acting user.
            required_role: The minimum role required for the operation.

        Returns:
            ``True`` if *user_role* >= *required_role* in the hierarchy.
        """
        return ROLE_HIERARCHY.get(user_role, -1) >= ROLE_HIERARCHY.get(
            required_role, 999
        )

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------

    def log_action(
        self,
        user_id: Optional[int],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[dict[str, object]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Append an entry to the audit trail.

        This method commits immediately so that audit records are persisted
        even if the outer request transaction is later rolled back.

        Args:
            user_id: Primary key of the acting user, or ``None`` for
                unauthenticated / system actions.
            action: Short action label, e.g. ``"LOGIN"``, ``"CREATE_ESTIMATION"``.
            resource_type: Name of the affected resource type, e.g.
                ``"estimation"``.
            resource_id: Primary key of the affected resource.
            details: Arbitrary extra context serialized to JSON.
            ip_address: Client IP address for the originating request.
        """
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details_json=json.dumps(details) if details else "{}",
            ip_address=ip_address,
        )
        self.session.add(entry)
        self.session.commit()

    def get_audit_log(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> list[AuditLog]:
        """Query the audit trail with optional filters.

        Results are returned in reverse chronological order (newest first).

        Args:
            limit: Maximum number of rows to return.
            offset: Number of rows to skip (for pagination).
            user_id: Filter to a specific acting user.
            action: Filter to a specific action label.
            resource_type: Filter to a specific resource type.

        Returns:
            List of ``AuditLog`` ORM instances.
        """
        q = self.session.query(AuditLog)
        if user_id is not None:
            q = q.filter(AuditLog.user_id == user_id)
        if action:
            q = q.filter(AuditLog.action == action)
        if resource_type:
            q = q.filter(AuditLog.resource_type == resource_type)
        return (
            q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
        )

    # ------------------------------------------------------------------
    # Bootstrap helper
    # ------------------------------------------------------------------

    def ensure_default_admin(self) -> None:
        """Create a default ``admin`` account if the users table is empty.

        This is called during application startup so that a fresh deployment
        always has at least one usable account.  The default password is
        ``admin`` and should be changed immediately in production.
        """
        user_count = self.session.query(User).count()
        if user_count == 0:
            self.create_user(
                username="admin",
                display_name="Administrator",
                password="admin",
                email="admin@localhost",
                role="ADMIN",
            )
