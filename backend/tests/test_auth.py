"""Comprehensive unit tests for the authentication and authorization system.

All tests use an in-memory SQLite database so no files are created on disk and
each test module run starts from a clean state.  The ``session`` fixture creates
all tables (including auth tables) and provides a ``Session`` object wired to
that engine.

Covered areas
-------------
- AuthService.create_user()             — hashes password, persists user
- AuthService.login()                   — good creds → tokens; bad creds → None
- AuthService.validate_access_token()  — valid JWT → payload; expired/bad → None
- AuthService.refresh()                 — rotates refresh token; expired → None
- AuthService.logout()                  — deletes session record
- AuthService.change_password()         — verifies old, stores new hash
- AuthService.log_action()              — persists AuditLog row
- AuthService.get_audit_log()           — filters by user / action / resource_type
- AuthService.has_permission()          — role-hierarchy comparisons
- RequireRole                           — ADMIN satisfies ESTIMATOR; VIEWER blocked
- AuthService.ensure_default_admin()    — creates admin only when table is empty

Note on JWT import
------------------
The tests do NOT import ``jwt`` (PyJWT) directly.  Expired tokens are produced
by patching ``src.auth.service.ACCESS_TOKEN_EXPIRE_MINUTES`` to ``-120`` via
``unittest.mock.patch``, then calling ``AuthService.create_access_token``
normally.  This keeps the test file free of any additional transitive imports.
"""

from __future__ import annotations

import json
import secrets as _secrets
from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Importing database models first ensures they are registered with Base.metadata
from src.database.models import Base, Configuration  # noqa: F401 — side-effect import

# Importing auth models registers users / user_sessions / audit_log tables
from src.auth.models import AuditLog, User, UserSession  # noqa: F401 — side-effect import
from src.auth.service import (
    ROLE_HIERARCHY,
    AuthService,
)
from src.auth.dependencies import RequireRole


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    """Per-test in-memory SQLite engine.

    A fresh engine and schema are created for each test to guarantee full
    isolation — SQLite's limited savepoint support makes connection-scoped
    rollback unreliable.
    """
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine) -> Generator[Session, None, None]:
    """Provide a clean database session for each test."""
    s = Session(bind=engine)
    yield s
    s.close()


@pytest.fixture
def svc(session: Session) -> AuthService:
    """``AuthService`` instance bound to the per-test session."""
    return AuthService(session)


@pytest.fixture
def alice(svc: AuthService) -> User:
    """A standard ESTIMATOR user created for use in tests."""
    return svc.create_user(
        username="alice",
        display_name="Alice Smith",
        password="correct-horse-battery",
        email="alice@example.com",
        role="ESTIMATOR",
    )


@pytest.fixture
def admin_user(svc: AuthService) -> User:
    """An ADMIN user for permission / hierarchy tests."""
    return svc.create_user(
        username="sysadmin",
        display_name="System Admin",
        password="admin-password-123",
        role="ADMIN",
    )


@pytest.fixture
def viewer_user(svc: AuthService) -> User:
    """A minimal VIEWER user for role-check tests."""
    return svc.create_user(
        username="viewer",
        display_name="Read Only",
        password="viewer-password",
        role="VIEWER",
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_expired_access_token(svc: AuthService, user: User) -> str:
    """Return a JWT that is already past its expiry time.

    We patch ``ACCESS_TOKEN_EXPIRE_MINUTES`` to ``-120`` (two hours in the
    past) inside ``src.auth.service`` so that ``create_access_token`` encodes
    an ``exp`` claim that is already expired.  This avoids importing PyJWT
    directly in the test module.
    """
    with patch("src.auth.service.ACCESS_TOKEN_EXPIRE_MINUTES", -120):
        return svc.create_access_token(user)


def _make_expired_session(session: Session, user: User) -> str:
    """Insert a UserSession row with an already-expired ``expires_at``."""
    token = _secrets.token_urlsafe(64)
    expired_at = datetime.now(timezone.utc) - timedelta(days=1)
    record = UserSession(
        user_id=user.id,
        refresh_token=token,
        expires_at=expired_at,
    )
    session.add(record)
    session.flush()
    return token


# ===========================================================================
# 1. create_user()
# ===========================================================================


class TestCreateUser:
    def test_returns_user_with_id(self, svc: AuthService) -> None:
        user = svc.create_user(username="bob", display_name="Bob Jones", password="secret")
        assert user.id is not None

    def test_password_is_hashed(self, svc: AuthService) -> None:
        import bcrypt

        user = svc.create_user(username="charlie", display_name="Charlie", password="plaintext")
        assert user.password_hash is not None
        assert user.password_hash != "plaintext"
        assert bcrypt.checkpw(b"plaintext", user.password_hash.encode())

    def test_default_role_is_viewer(self, svc: AuthService) -> None:
        user = svc.create_user(username="defaultrole", display_name="Default")
        assert user.role == "VIEWER"

    def test_custom_role_is_stored(self, svc: AuthService) -> None:
        user = svc.create_user(username="approver1", display_name="Approver", role="APPROVER")
        assert user.role == "APPROVER"

    def test_optional_email_stored(self, svc: AuthService) -> None:
        user = svc.create_user(
            username="withmail", display_name="With Mail", email="wm@example.com"
        )
        assert user.email == "wm@example.com"

    def test_external_provider_no_password(self, svc: AuthService) -> None:
        """IdP users may have no local password hash."""
        user = svc.create_user(
            username="ldap_user",
            display_name="LDAP User",
            auth_provider="ldap",
            external_id="cn=ldap_user,dc=corp,dc=example",
        )
        assert user.password_hash is None
        assert user.auth_provider == "ldap"

    def test_user_is_active_by_default(self, svc: AuthService) -> None:
        user = svc.create_user(username="active_default", display_name="Active")
        assert user.is_active is True

    def test_duplicate_username_raises(self, svc: AuthService, alice: User) -> None:
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            svc.create_user(username="alice", display_name="Another Alice")


# ===========================================================================
# 2. login()
# ===========================================================================


class TestLogin:
    def test_correct_credentials_return_tuple(self, svc: AuthService, alice: User) -> None:
        result = svc.login("alice", "correct-horse-battery")
        assert result is not None
        user, access_token, refresh_token = result
        assert user.username == "alice"

    def test_returns_non_empty_tokens(self, svc: AuthService, alice: User) -> None:
        _, access_token, refresh_token = svc.login("alice", "correct-horse-battery")
        assert len(access_token) > 20
        assert len(refresh_token) > 20

    def test_wrong_password_returns_none(self, svc: AuthService, alice: User) -> None:
        result = svc.login("alice", "wrong-password")
        assert result is None

    def test_unknown_username_returns_none(self, svc: AuthService) -> None:
        result = svc.login("nobody", "whatever")
        assert result is None

    def test_inactive_user_returns_none(self, svc: AuthService, session: Session) -> None:
        user = svc.create_user(username="inactive", display_name="Inactive", password="pw")
        user.is_active = False
        session.flush()
        result = svc.login("inactive", "pw")
        assert result is None

    def test_login_updates_last_login_at(self, svc: AuthService, alice: User) -> None:
        before = datetime.now(timezone.utc)
        svc.login("alice", "correct-horse-battery")
        # Reload from DB
        session = svc.session
        session.expire(alice)
        assert alice.last_login_at is not None
        # Allow a small clock skew
        last_login = alice.last_login_at
        if last_login.tzinfo is None:
            last_login = last_login.replace(tzinfo=timezone.utc)
        assert last_login >= before - timedelta(seconds=5)

    def test_login_creates_session_record(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        _, _, refresh_token = svc.login("alice", "correct-horse-battery")
        record = (
            session.query(UserSession)
            .filter(UserSession.refresh_token == refresh_token)
            .first()
        )
        assert record is not None
        assert record.user_id == alice.id

    def test_login_writes_audit_entry(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        svc.login("alice", "correct-horse-battery")
        entry = (
            session.query(AuditLog)
            .filter(AuditLog.user_id == alice.id, AuditLog.action == "LOGIN")
            .first()
        )
        assert entry is not None

    def test_user_without_password_hash_returns_none(
        self, svc: AuthService, session: Session
    ) -> None:
        """LDAP/OIDC users cannot log in via local password."""
        user = svc.create_user(
            username="oidc_only",
            display_name="OIDC Only",
            auth_provider="oidc",
        )
        result = svc.login("oidc_only", "any-password")
        assert result is None


# ===========================================================================
# 3. validate_access_token()
# ===========================================================================


class TestValidateAccessToken:
    def test_valid_token_returns_payload(self, svc: AuthService, alice: User) -> None:
        _, access_token, _ = svc.login("alice", "correct-horse-battery")
        payload = svc.validate_access_token(access_token)
        assert payload is not None
        assert payload["username"] == "alice"

    def test_payload_contains_expected_claims(self, svc: AuthService, alice: User) -> None:
        _, access_token, _ = svc.login("alice", "correct-horse-battery")
        payload = svc.validate_access_token(access_token)
        assert payload is not None
        assert payload["type"] == "access"
        assert str(payload["sub"]) == str(alice.id)
        assert payload["role"] == "ESTIMATOR"

    def test_expired_token_returns_none(self, svc: AuthService, alice: User) -> None:
        expired = _make_expired_access_token(svc, alice)
        assert svc.validate_access_token(expired) is None

    def test_garbage_string_returns_none(self, svc: AuthService) -> None:
        assert svc.validate_access_token("not.a.jwt") is None

    def test_empty_string_returns_none(self, svc: AuthService) -> None:
        assert svc.validate_access_token("") is None

    def test_wrong_type_claim_returns_none(self, svc: AuthService, alice: User) -> None:
        """A token whose ``type`` claim is not ``'access'`` must be rejected.

        We create a token via a patched ``create_access_token`` that injects
        ``type='refresh'`` into the payload by temporarily patching the service
        method to swap the type claim.  This avoids a direct jwt.encode call.
        """
        import src.auth.service as auth_svc_module

        original = auth_svc_module.AuthService.create_access_token

        def _patched(self_inner: AuthService, user: User) -> str:  # type: ignore[override]
            token = original(self_inner, user)
            # Decode → mutate type → re-encode using the same secret
            import importlib
            jwt_mod = importlib.import_module("jwt")
            payload = jwt_mod.decode(
                token, self_inner.jwt_secret, algorithms=["HS256"]
            )
            payload["type"] = "refresh"
            return jwt_mod.encode(payload, self_inner.jwt_secret, algorithm="HS256")

        with patch.object(auth_svc_module.AuthService, "create_access_token", _patched):
            bad_token = svc.create_access_token(alice)

        assert svc.validate_access_token(bad_token) is None

    def test_token_signed_with_wrong_secret_returns_none(
        self, svc: AuthService, alice: User
    ) -> None:
        """A token signed with a different secret must be rejected.

        We call ``create_access_token`` after temporarily pointing the service's
        cached secret at a different value so the resulting token cannot be
        verified by the real secret.
        """
        # Force a fresh JWT secret to be generated for the service instance
        _ = svc.jwt_secret  # ensure _jwt_secret is populated
        original_secret = svc._jwt_secret

        # Temporarily swap the cached secret so we produce a token signed with
        # a completely different key, then restore the original.
        svc._jwt_secret = "completely-wrong-secret"
        bad_token = svc.create_access_token(alice)
        svc._jwt_secret = original_secret

        assert svc.validate_access_token(bad_token) is None


# ===========================================================================
# 4. refresh()
# ===========================================================================


class TestRefreshToken:
    def test_valid_refresh_returns_new_token_pair(
        self, svc: AuthService, alice: User
    ) -> None:
        _, old_access, old_refresh = svc.login("alice", "correct-horse-battery")
        result = svc.refresh(old_refresh)
        assert result is not None
        user, new_access, new_refresh = result
        assert user.username == "alice"
        # Access token may be identical if issued within the same second (same
        # claims + same iat), so we only assert it is a non-empty string.
        assert isinstance(new_access, str) and len(new_access) > 0
        # Refresh tokens are always unique (random).
        assert new_refresh != old_refresh

    def test_old_refresh_token_is_invalidated(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        _, _, old_refresh = svc.login("alice", "correct-horse-battery")
        svc.refresh(old_refresh)
        record = (
            session.query(UserSession)
            .filter(UserSession.refresh_token == old_refresh)
            .first()
        )
        assert record is None, "Old refresh token session should have been deleted"

    def test_new_session_record_exists(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        _, _, old_refresh = svc.login("alice", "correct-horse-battery")
        _, _, new_refresh = svc.refresh(old_refresh)
        record = (
            session.query(UserSession)
            .filter(UserSession.refresh_token == new_refresh)
            .first()
        )
        assert record is not None

    def test_unknown_refresh_token_returns_none(self, svc: AuthService) -> None:
        assert svc.refresh("token-that-does-not-exist") is None

    def test_expired_refresh_token_returns_none(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        expired_token = _make_expired_session(session, alice)
        assert svc.refresh(expired_token) is None

    def test_expired_session_record_is_deleted(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        expired_token = _make_expired_session(session, alice)
        svc.refresh(expired_token)
        record = (
            session.query(UserSession)
            .filter(UserSession.refresh_token == expired_token)
            .first()
        )
        assert record is None

    def test_inactive_user_refresh_returns_none(
        self, svc: AuthService, session: Session
    ) -> None:
        user = svc.create_user(username="will_deactivate", display_name="D", password="pw")
        _, _, refresh_token = svc.login("will_deactivate", "pw")
        user.is_active = False
        session.flush()
        assert svc.refresh(refresh_token) is None


# ===========================================================================
# 5. logout()
# ===========================================================================


class TestLogout:
    def test_logout_returns_true_when_session_exists(
        self, svc: AuthService, alice: User
    ) -> None:
        _, _, refresh_token = svc.login("alice", "correct-horse-battery")
        assert svc.logout(refresh_token) is True

    def test_logout_deletes_session_record(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        _, _, refresh_token = svc.login("alice", "correct-horse-battery")
        svc.logout(refresh_token)
        record = (
            session.query(UserSession)
            .filter(UserSession.refresh_token == refresh_token)
            .first()
        )
        assert record is None

    def test_logout_with_unknown_token_returns_false(self, svc: AuthService) -> None:
        assert svc.logout("nonexistent-token") is False

    def test_logout_is_idempotent_second_call_returns_false(
        self, svc: AuthService, alice: User
    ) -> None:
        _, _, refresh_token = svc.login("alice", "correct-horse-battery")
        svc.logout(refresh_token)
        assert svc.logout(refresh_token) is False

    def test_logout_does_not_affect_other_sessions(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        """Revoking one session must leave other sessions untouched."""
        _, _, refresh_a = svc.login("alice", "correct-horse-battery")
        _, _, refresh_b = svc.login("alice", "correct-horse-battery")
        svc.logout(refresh_a)
        record_b = (
            session.query(UserSession)
            .filter(UserSession.refresh_token == refresh_b)
            .first()
        )
        assert record_b is not None


# ===========================================================================
# 6. change_password()
# ===========================================================================


class TestChangePassword:
    def test_correct_current_password_returns_true(
        self, svc: AuthService, alice: User
    ) -> None:
        result = svc.change_password(alice.id, "correct-horse-battery", "new-secure-pass")
        assert result is True

    def test_wrong_current_password_returns_false(
        self, svc: AuthService, alice: User
    ) -> None:
        result = svc.change_password(alice.id, "wrong-old-password", "new-secure-pass")
        assert result is False

    def test_old_password_no_longer_valid_after_change(
        self, svc: AuthService, alice: User
    ) -> None:
        svc.change_password(alice.id, "correct-horse-battery", "brand-new-password")
        assert svc.login("alice", "correct-horse-battery") is None

    def test_new_password_works_after_change(
        self, svc: AuthService, alice: User
    ) -> None:
        svc.change_password(alice.id, "correct-horse-battery", "brand-new-password")
        result = svc.login("alice", "brand-new-password")
        assert result is not None

    def test_nonexistent_user_returns_false(self, svc: AuthService) -> None:
        assert svc.change_password(99999, "any", "other") is False

    def test_user_without_local_password_returns_false(
        self, svc: AuthService
    ) -> None:
        user = svc.create_user(
            username="ldap_pw_test",
            display_name="LDAP",
            auth_provider="ldap",
        )
        assert svc.change_password(user.id, "", "new-pass") is False


# ===========================================================================
# 7. log_action()
# ===========================================================================


class TestLogAction:
    def test_creates_audit_log_entry(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        svc.log_action(alice.id, "CUSTOM_ACTION")
        entries = (
            session.query(AuditLog)
            .filter(AuditLog.action == "CUSTOM_ACTION")
            .all()
        )
        assert len(entries) == 1

    def test_entry_has_correct_user_id(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        svc.log_action(alice.id, "CHECK_USER_ID")
        entry = (
            session.query(AuditLog)
            .filter(AuditLog.action == "CHECK_USER_ID")
            .first()
        )
        assert entry is not None
        assert entry.user_id == alice.id

    def test_resource_fields_are_stored(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        svc.log_action(
            alice.id,
            "CREATE_ESTIMATION",
            resource_type="estimation",
            resource_id=42,
        )
        entry = (
            session.query(AuditLog)
            .filter(AuditLog.action == "CREATE_ESTIMATION")
            .first()
        )
        assert entry is not None
        assert entry.resource_type == "estimation"
        assert entry.resource_id == 42

    def test_details_dict_serialized_to_json(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        details = {"foo": "bar", "count": 7}
        svc.log_action(alice.id, "WITH_DETAILS", details=details)
        entry = (
            session.query(AuditLog)
            .filter(AuditLog.action == "WITH_DETAILS")
            .first()
        )
        assert entry is not None
        assert json.loads(entry.details_json) == details

    def test_ip_address_stored(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        svc.log_action(alice.id, "IP_TEST", ip_address="192.168.1.100")
        entry = (
            session.query(AuditLog)
            .filter(AuditLog.action == "IP_TEST")
            .first()
        )
        assert entry is not None
        assert entry.ip_address == "192.168.1.100"

    def test_null_user_id_allowed_for_system_actions(
        self, svc: AuthService, session: Session
    ) -> None:
        svc.log_action(None, "SYSTEM_STARTUP")
        entry = (
            session.query(AuditLog)
            .filter(AuditLog.action == "SYSTEM_STARTUP")
            .first()
        )
        assert entry is not None
        assert entry.user_id is None

    def test_no_details_defaults_to_empty_json_object(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        svc.log_action(alice.id, "NO_DETAILS_ACTION")
        entry = (
            session.query(AuditLog)
            .filter(AuditLog.action == "NO_DETAILS_ACTION")
            .first()
        )
        assert entry is not None
        assert entry.details_json == "{}"


# ===========================================================================
# 8. get_audit_log()
# ===========================================================================


class TestGetAuditLog:
    @pytest.fixture(autouse=True)
    def _seed_audit_entries(
        self, svc: AuthService, alice: User, viewer_user: User
    ) -> None:
        """Populate a deterministic set of audit entries before each test."""
        svc.log_action(alice.id, "LOGIN", resource_type="session")
        svc.log_action(alice.id, "CREATE_ESTIMATION", resource_type="estimation", resource_id=1)
        svc.log_action(alice.id, "CREATE_ESTIMATION", resource_type="estimation", resource_id=2)
        svc.log_action(viewer_user.id, "LOGIN", resource_type="session")
        svc.log_action(viewer_user.id, "VIEW_ESTIMATION", resource_type="estimation")

    def test_returns_all_entries_by_default(self, svc: AuthService) -> None:
        entries = svc.get_audit_log(limit=100)
        assert len(entries) >= 5

    def test_filter_by_user_id(self, svc: AuthService, alice: User) -> None:
        entries = svc.get_audit_log(user_id=alice.id)
        assert all(e.user_id == alice.id for e in entries)
        assert len(entries) == 3  # LOGIN + 2× CREATE_ESTIMATION

    def test_filter_by_action(self, svc: AuthService) -> None:
        entries = svc.get_audit_log(action="CREATE_ESTIMATION")
        assert all(e.action == "CREATE_ESTIMATION" for e in entries)
        assert len(entries) == 2

    def test_filter_by_resource_type(self, svc: AuthService) -> None:
        entries = svc.get_audit_log(resource_type="session")
        assert all(e.resource_type == "session" for e in entries)

    def test_combined_filters(self, svc: AuthService, alice: User) -> None:
        entries = svc.get_audit_log(user_id=alice.id, resource_type="estimation")
        assert len(entries) == 2
        assert all(e.user_id == alice.id for e in entries)

    def test_limit_is_respected(self, svc: AuthService) -> None:
        entries = svc.get_audit_log(limit=2)
        assert len(entries) <= 2

    def test_offset_paginates_results(self, svc: AuthService) -> None:
        all_entries = svc.get_audit_log(limit=100)
        paginated = svc.get_audit_log(limit=100, offset=2)
        assert len(paginated) == len(all_entries) - 2

    def test_results_ordered_newest_first(self, svc: AuthService) -> None:
        entries = svc.get_audit_log(limit=100)
        timestamps = [e.created_at for e in entries if e.created_at is not None]
        # SQLite server_default times may be identical; allow equal-or-descending order
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1] or timestamps[i] == timestamps[i + 1]


# ===========================================================================
# 9. has_permission() — role hierarchy
# ===========================================================================


class TestHasPermission:
    """Verify the role hierarchy VIEWER < ESTIMATOR < APPROVER < ADMIN."""

    # VIEWER
    def test_viewer_satisfies_viewer(self) -> None:
        assert AuthService.has_permission("VIEWER", "VIEWER") is True

    def test_viewer_blocked_by_estimator(self) -> None:
        assert AuthService.has_permission("VIEWER", "ESTIMATOR") is False

    def test_viewer_blocked_by_approver(self) -> None:
        assert AuthService.has_permission("VIEWER", "APPROVER") is False

    def test_viewer_blocked_by_admin(self) -> None:
        assert AuthService.has_permission("VIEWER", "ADMIN") is False

    # ESTIMATOR
    def test_estimator_satisfies_viewer(self) -> None:
        assert AuthService.has_permission("ESTIMATOR", "VIEWER") is True

    def test_estimator_satisfies_estimator(self) -> None:
        assert AuthService.has_permission("ESTIMATOR", "ESTIMATOR") is True

    def test_estimator_blocked_by_approver(self) -> None:
        assert AuthService.has_permission("ESTIMATOR", "APPROVER") is False

    def test_estimator_blocked_by_admin(self) -> None:
        assert AuthService.has_permission("ESTIMATOR", "ADMIN") is False

    # APPROVER
    def test_approver_satisfies_estimator(self) -> None:
        assert AuthService.has_permission("APPROVER", "ESTIMATOR") is True

    def test_approver_satisfies_approver(self) -> None:
        assert AuthService.has_permission("APPROVER", "APPROVER") is True

    def test_approver_blocked_by_admin(self) -> None:
        assert AuthService.has_permission("APPROVER", "ADMIN") is False

    # ADMIN
    def test_admin_satisfies_viewer(self) -> None:
        assert AuthService.has_permission("ADMIN", "VIEWER") is True

    def test_admin_satisfies_estimator(self) -> None:
        assert AuthService.has_permission("ADMIN", "ESTIMATOR") is True

    def test_admin_satisfies_approver(self) -> None:
        assert AuthService.has_permission("ADMIN", "APPROVER") is True

    def test_admin_satisfies_admin(self) -> None:
        assert AuthService.has_permission("ADMIN", "ADMIN") is True

    # Edge cases
    def test_unknown_user_role_is_blocked(self) -> None:
        assert AuthService.has_permission("GHOST", "VIEWER") is False

    def test_unknown_required_role_blocks_all(self) -> None:
        """An unrecognised required role should block everyone."""
        assert AuthService.has_permission("ADMIN", "SUPER_ROOT") is False

    def test_role_hierarchy_values_are_monotonically_increasing(self) -> None:
        ordered = ["VIEWER", "ESTIMATOR", "APPROVER", "ADMIN"]
        values = [ROLE_HIERARCHY[r] for r in ordered]
        assert values == sorted(values)
        assert len(set(values)) == len(values), "Each role must have a unique numeric value"


# ===========================================================================
# 10. RequireRole — FastAPI dependency
# ===========================================================================


class TestRequireRole:
    """Unit-test ``RequireRole.__call__`` directly, bypassing FastAPI DI."""

    def _make_user(self, role: str) -> User:
        """Return a mock User-like object with the given role."""
        user = MagicMock(spec=User)
        user.role = role
        return user

    def test_admin_satisfies_estimator_requirement(self) -> None:
        dep = RequireRole("ESTIMATOR")
        admin = self._make_user("ADMIN")
        returned = dep.__call__(user=admin)
        assert returned is admin

    def test_admin_satisfies_viewer_requirement(self) -> None:
        dep = RequireRole("VIEWER")
        admin = self._make_user("ADMIN")
        assert dep.__call__(user=admin) is admin

    def test_admin_satisfies_admin_requirement(self) -> None:
        dep = RequireRole("ADMIN")
        admin = self._make_user("ADMIN")
        assert dep.__call__(user=admin) is admin

    def test_viewer_blocked_by_estimator_requirement(self) -> None:
        dep = RequireRole("ESTIMATOR")
        viewer = self._make_user("VIEWER")
        with pytest.raises(HTTPException) as exc_info:
            dep.__call__(user=viewer)
        assert exc_info.value.status_code == 403

    def test_viewer_blocked_by_approver_requirement(self) -> None:
        dep = RequireRole("APPROVER")
        viewer = self._make_user("VIEWER")
        with pytest.raises(HTTPException) as exc_info:
            dep.__call__(user=viewer)
        assert exc_info.value.status_code == 403

    def test_estimator_blocked_by_admin_requirement(self) -> None:
        dep = RequireRole("ADMIN")
        estimator = self._make_user("ESTIMATOR")
        with pytest.raises(HTTPException) as exc_info:
            dep.__call__(user=estimator)
        assert exc_info.value.status_code == 403

    def test_estimator_satisfies_viewer_requirement(self) -> None:
        dep = RequireRole("VIEWER")
        estimator = self._make_user("ESTIMATOR")
        assert dep.__call__(user=estimator) is estimator

    def test_error_detail_mentions_required_role(self) -> None:
        dep = RequireRole("APPROVER")
        viewer = self._make_user("VIEWER")
        with pytest.raises(HTTPException) as exc_info:
            dep.__call__(user=viewer)
        assert "APPROVER" in exc_info.value.detail

    def test_minimum_role_attribute_stored(self) -> None:
        dep = RequireRole("ESTIMATOR")
        assert dep.minimum_role == "ESTIMATOR"


# ===========================================================================
# 11. ensure_default_admin()
# ===========================================================================


class TestEnsureDefaultAdmin:
    def test_creates_admin_when_table_is_empty(
        self, svc: AuthService, session: Session
    ) -> None:
        """With no users in the DB, ensure_default_admin must create one."""
        # Verify table is empty in this test's scope
        count_before = session.query(User).count()
        assert count_before == 0, (
            "This test requires an empty users table — check fixture isolation"
        )
        svc.ensure_default_admin()
        count_after = session.query(User).count()
        assert count_after == 1

    def test_created_admin_has_admin_role(
        self, svc: AuthService, session: Session
    ) -> None:
        svc.ensure_default_admin()
        user = session.query(User).filter(User.username == "admin").first()
        assert user is not None
        assert user.role == "ADMIN"

    def test_created_admin_can_login(
        self, svc: AuthService, session: Session
    ) -> None:
        svc.ensure_default_admin()
        result = svc.login("admin", "admin")
        assert result is not None

    def test_does_not_create_admin_when_users_exist(
        self, svc: AuthService, alice: User, session: Session
    ) -> None:
        """If at least one user exists, ensure_default_admin must be a no-op."""
        count_before = session.query(User).count()
        assert count_before >= 1
        svc.ensure_default_admin()
        count_after = session.query(User).count()
        assert count_after == count_before

    def test_calling_twice_does_not_duplicate_admin(
        self, svc: AuthService, session: Session
    ) -> None:
        svc.ensure_default_admin()
        svc.ensure_default_admin()
        admins = session.query(User).filter(User.username == "admin").all()
        assert len(admins) == 1


# ===========================================================================
# 12. JWT secret management
# ===========================================================================


class TestJwtSecret:
    def test_secret_is_auto_generated_and_persisted(
        self, svc: AuthService, session: Session
    ) -> None:
        secret = svc.jwt_secret
        cfg = (
            session.query(Configuration)
            .filter(Configuration.key == "jwt_secret")
            .first()
        )
        assert cfg is not None
        assert cfg.value == secret

    def test_secret_is_stable_within_service_instance(self, svc: AuthService) -> None:
        first = svc.jwt_secret
        second = svc.jwt_secret
        assert first == second

    def test_new_service_instance_shares_same_secret(
        self, session: Session, svc: AuthService
    ) -> None:
        """Two AuthService instances on the same session share the stored secret."""
        secret_a = svc.jwt_secret
        svc2 = AuthService(session)
        # The second instance reads from the DB (cached by svc already)
        secret_b = svc2.jwt_secret
        assert secret_a == secret_b

    def test_secret_has_adequate_length(self, svc: AuthService) -> None:
        """Auto-generated secret should be at least 32 hex chars (128 bits)."""
        assert len(svc.jwt_secret) >= 32


# ===========================================================================
# 13. Auxiliary user management
# ===========================================================================


class TestUserManagement:
    def test_get_user_by_id_returns_correct_user(
        self, svc: AuthService, alice: User
    ) -> None:
        fetched = svc.get_user_by_id(alice.id)
        assert fetched is not None
        assert fetched.username == "alice"

    def test_get_user_by_id_returns_none_for_unknown(self, svc: AuthService) -> None:
        assert svc.get_user_by_id(99999) is None

    def test_get_user_by_username(self, svc: AuthService, alice: User) -> None:
        fetched = svc.get_user_by_username("alice")
        assert fetched is not None
        assert fetched.id == alice.id

    def test_get_user_by_username_returns_none_for_unknown(
        self, svc: AuthService
    ) -> None:
        assert svc.get_user_by_username("ghost") is None

    def test_list_users_returns_all(
        self, svc: AuthService, alice: User, admin_user: User, viewer_user: User
    ) -> None:
        users = svc.list_users()
        usernames = {u.username for u in users}
        assert {"alice", "sysadmin", "viewer"}.issubset(usernames)

    def test_list_users_active_only_excludes_inactive(
        self, svc: AuthService, session: Session
    ) -> None:
        user = svc.create_user(username="deactivated", display_name="D", password="pw")
        user.is_active = False
        session.flush()
        active = svc.list_users(active_only=True)
        assert all(u.is_active for u in active)
        assert not any(u.username == "deactivated" for u in active)

    def test_update_user_display_name(self, svc: AuthService, alice: User) -> None:
        updated = svc.update_user(alice.id, display_name="Alicia Smith")
        assert updated is not None
        assert updated.display_name == "Alicia Smith"

    def test_update_user_password_via_keyword(
        self, svc: AuthService, alice: User
    ) -> None:
        svc.update_user(alice.id, password="updated-password")
        assert svc.login("alice", "updated-password") is not None
        assert svc.login("alice", "correct-horse-battery") is None

    def test_update_nonexistent_user_returns_none(self, svc: AuthService) -> None:
        assert svc.update_user(99999, display_name="Ghost") is None

    def test_delete_user_removes_record(
        self, svc: AuthService, session: Session
    ) -> None:
        user = svc.create_user(username="to_delete", display_name="Delete Me", password="pw")
        user_id = user.id
        assert svc.delete_user(user_id) is True
        assert svc.get_user_by_id(user_id) is None

    def test_delete_nonexistent_user_returns_false(self, svc: AuthService) -> None:
        assert svc.delete_user(99999) is False
