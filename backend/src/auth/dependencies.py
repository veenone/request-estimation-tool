"""FastAPI dependency injection helpers for authentication and authorization.

These dependencies are intended to be used with ``Depends()`` in route
function signatures.  They extract the JWT from the ``Authorization`` header,
validate it, and return the corresponding ``User`` ORM instance.

Usage example::

    from fastapi import APIRouter, Depends
    from .dependencies import get_current_user, require_role

    router = APIRouter()

    @router.get("/estimations")
    def list_estimations(user = Depends(get_current_user)):
        ...  # any authenticated user

    @router.post("/estimations/{id}/approve")
    def approve(id: int, user = require_role("APPROVER")):
        ...  # only APPROVER or ADMIN
"""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .models import User
from .service import AuthService


def _get_db():
    """Lazy import of get_db to avoid circular imports.

    ``auth.dependencies`` is imported by ``api.routes``, which is imported by
    ``api.app``.  Importing ``api.app.get_db`` at module level here would
    therefore create a circular dependency.  We resolve it by deferring the
    import to call time.

    The function also respects ``app.dependency_overrides`` so that tests
    which override ``get_db`` also affect auth dependencies.
    """
    from ..api.app import app, get_db as _gdb
    fn = app.dependency_overrides.get(_gdb, _gdb)
    yield from fn()


def get_current_user(
    request: Request, db: Session = Depends(_get_db)
) -> User:
    """Extract and validate the JWT bearer token from the request.

    Reads the ``Authorization: Bearer <token>`` header, validates the JWT
    signature and expiry, and returns the corresponding active ``User``
    instance.

    Args:
        request: The incoming FastAPI ``Request`` object.
        db: SQLAlchemy session provided by ``get_db``.

    Returns:
        The authenticated ``User`` ORM instance.

    Raises:
        HTTPException 401: When the header is missing, the token is invalid
            or expired, or the associated user does not exist / is inactive.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ", 1)[1]
    auth_service = AuthService(db)
    payload = auth_service.validate_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_service.get_user_by_id(int(str(payload["sub"])))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


def get_optional_user(
    request: Request, db: Session = Depends(_get_db)
) -> Optional[User]:
    """Like ``get_current_user`` but returns ``None`` instead of raising 401.

    Useful for endpoints that behave differently for authenticated vs
    anonymous callers without outright rejecting unauthenticated requests.

    Args:
        request: The incoming FastAPI ``Request`` object.
        db: SQLAlchemy session provided by ``get_db``.

    Returns:
        The authenticated ``User`` instance, or ``None`` when no valid token
        is present.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1]
    auth_service = AuthService(db)
    payload = auth_service.validate_access_token(token)

    if payload is None:
        return None

    user = auth_service.get_user_by_id(int(str(payload["sub"])))
    if not user or not user.is_active:
        return None

    return user


class RequireRole:
    """Callable dependency class that enforces a minimum role level.

    Designed to be instantiated once and reused as a dependency, following
    FastAPI's recommended pattern for parameterized dependencies.

    Example::

        require_admin = RequireRole("ADMIN")

        @router.delete("/users/{id}")
        def delete_user(id: int, user: User = Depends(require_admin)):
            ...
    """

    def __init__(self, minimum_role: str) -> None:
        """
        Args:
            minimum_role: The minimum role required to access the endpoint.
                Must be one of ``VIEWER``, ``ESTIMATOR``, ``APPROVER``,
                or ``ADMIN``.
        """
        self.minimum_role = minimum_role

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        """Validate that the current user has the required role.

        Args:
            user: Current authenticated user from ``get_current_user``.

        Returns:
            The ``User`` instance when permission is granted.

        Raises:
            HTTPException 403: When the user's role is below ``minimum_role``.
        """
        if not AuthService.has_permission(user.role, self.minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient permissions. Required role: {self.minimum_role}"
                ),
            )
        return user


def require_role(role: str) -> User:
    """Factory that returns a ``Depends(RequireRole(role))`` dependency.

    Allows inline role requirements without creating a named ``RequireRole``
    instance::

        @router.post("/estimations/{id}/approve")
        def approve(id: int, user: User = require_role("APPROVER")):
            ...

    Args:
        role: The minimum role string required for the route.

    Returns:
        A FastAPI ``Depends`` object wrapping a ``RequireRole`` instance.
    """
    return Depends(RequireRole(role))  # type: ignore[return-value]
