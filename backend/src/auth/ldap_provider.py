"""LDAP / Active Directory authentication and user synchronization.

``LDAPProvider`` handles two distinct use cases:

1. **Interactive login** (``authenticate``): a user supplies their AD
   credentials; the provider performs a bind-as-user verification and
   creates or updates the corresponding local ``User`` row.

2. **Bulk sync** (``sync_users``): a scheduled or admin-triggered operation
   that enumerates all directory entries and mirrors their state (including
   disabled accounts) into the local database.

Configuration is stored in the ``configuration`` table under the following
keys:

- ``ldap_url`` — LDAP server URI, e.g. ``ldap://dc.example.com``
- ``ldap_bind_dn`` — Service account DN used for initial searches
- ``ldap_bind_password`` — Password for the service account
- ``ldap_search_base`` — Base DN for all search operations
- ``ldap_user_filter`` — Search filter template; ``{username}`` is replaced
  at runtime, e.g. ``(sAMAccountName={username})``
- ``ldap_group_mapping_json`` — JSON mapping of app roles to AD group DNs,
  e.g. ``{"ADMIN": "CN=EstimationAdmins,OU=Groups,DC=example,DC=com"}``

The ``ldap3`` library is an optional runtime dependency.  All methods
return gracefully (``None`` / empty result) when the library is not installed
or when LDAP is not configured.
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from ..database.models import Configuration
from .models import User


class LDAPProvider:
    """LDAP authentication provider for Active Directory integration."""

    def __init__(self, session: Session) -> None:
        """
        Args:
            session: Active SQLAlchemy session used for reading config and
                writing user records.
        """
        self.session = session
        self._config: Optional[dict[str, str]] = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def config(self) -> dict[str, str]:
        """Lazily load LDAP configuration from the ``configuration`` table."""
        if self._config is None:
            self._config = {}
            keys = (
                "ldap_url",
                "ldap_bind_dn",
                "ldap_bind_password",
                "ldap_search_base",
                "ldap_user_filter",
                "ldap_group_mapping_json",
            )
            for key in keys:
                cfg = (
                    self.session.query(Configuration)
                    .filter(Configuration.key == key)
                    .first()
                )
                self._config[key] = cfg.value if cfg else ""
        return self._config

    @property
    def is_configured(self) -> bool:
        """Return ``True`` when a non-empty ``ldap_url`` is configured."""
        return bool(self.config.get("ldap_url"))

    # ------------------------------------------------------------------
    # Interactive login
    # ------------------------------------------------------------------

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate *username* against LDAP and sync the local record.

        Steps:

        1. Bind with the service account and search for the user entry.
        2. Re-bind as the user to verify their password.
        3. Map AD group memberships to an application role.
        4. Create or update the local ``User`` row.

        Args:
            username: The AD samAccountName / login name.
            password: The user's plaintext AD password.

        Returns:
            The local ``User`` instance on success, ``None`` on any failure
            (wrong credentials, user not found, library not installed, etc.).
        """
        if not self.is_configured:
            return None

        try:
            import ldap3  # type: ignore[import-untyped]

            server = ldap3.Server(self.config["ldap_url"], get_info=ldap3.ALL)

            search_base = self.config.get("ldap_search_base", "")
            user_filter_tpl = self.config.get(
                "ldap_user_filter", "(sAMAccountName={username})"
            )
            user_filter = user_filter_tpl.replace("{username}", username)

            # Step 1: bind with service account and search.
            conn = ldap3.Connection(
                server,
                user=self.config.get("ldap_bind_dn"),
                password=self.config.get("ldap_bind_password"),
                auto_bind=True,
            )
            conn.search(
                search_base,
                user_filter,
                attributes=["cn", "mail", "memberOf", "distinguishedName"],
            )

            if not conn.entries:
                return None

            entry = conn.entries[0]
            user_dn = str(entry.entry_dn)

            # Step 2: verify the user's password by binding as them.
            user_conn = ldap3.Connection(server, user=user_dn, password=password)
            if not user_conn.bind():
                return None

            # Step 3: extract attributes and map to application role.
            display_name = (
                str(entry.cn) if hasattr(entry, "cn") and entry.cn else username
            )
            email: Optional[str] = (
                str(entry.mail) if hasattr(entry, "mail") and entry.mail else None
            )
            groups: list[str] = (
                [str(g) for g in entry.memberOf]
                if hasattr(entry, "memberOf") and entry.memberOf
                else []
            )
            role = self._map_groups_to_role(groups)

            # Step 4: upsert local user.
            local_user = (
                self.session.query(User).filter(User.username == username).first()
            )
            if local_user:
                local_user.display_name = display_name
                local_user.email = email
                local_user.external_id = user_dn
                local_user.role = role
                local_user.is_active = True
            else:
                local_user = User(
                    username=username,
                    display_name=display_name,
                    email=email,
                    auth_provider="ldap",
                    external_id=user_dn,
                    role=role,
                    is_active=True,
                )
                self.session.add(local_user)

            self.session.commit()
            self.session.refresh(local_user)
            return local_user

        except ImportError:
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Bulk sync
    # ------------------------------------------------------------------

    def sync_users(self) -> dict[str, object]:
        """Enumerate all LDAP users and mirror their state locally.

        - New directory entries are created as local ``User`` rows.
        - Existing local users are updated with current directory attributes.
        - Local LDAP users whose entries are no longer present in the
          directory are deactivated (not deleted).

        Returns:
            A summary dict with keys ``synced``, ``created``, ``updated``,
            ``deactivated``, and ``errors`` (list of error strings).
        """
        result: dict[str, object] = {
            "synced": 0,
            "created": 0,
            "updated": 0,
            "deactivated": 0,
            "errors": [],
        }

        if not self.is_configured:
            return result

        try:
            import ldap3  # type: ignore[import-untyped]

            server = ldap3.Server(self.config["ldap_url"], get_info=ldap3.ALL)
            conn = ldap3.Connection(
                server,
                user=self.config.get("ldap_bind_dn"),
                password=self.config.get("ldap_bind_password"),
                auto_bind=True,
            )

            search_base = self.config.get("ldap_search_base", "")
            # When used for sync the filter should enumerate all users.
            user_filter = self.config.get("ldap_user_filter", "(objectClass=person)")
            # Strip the {username} placeholder if it was left in the template.
            user_filter = user_filter.replace("{username}", "*")

            conn.search(
                search_base,
                user_filter,
                attributes=[
                    "sAMAccountName",
                    "cn",
                    "mail",
                    "memberOf",
                    "distinguishedName",
                    "userAccountControl",
                ],
            )

            ldap_usernames: set[str] = set()
            errors: list[str] = []

            for entry in conn.entries:
                try:
                    sam = (
                        str(entry.sAMAccountName)
                        if hasattr(entry, "sAMAccountName") and entry.sAMAccountName
                        else None
                    )
                    if not sam:
                        continue

                    ldap_usernames.add(sam)

                    display_name = (
                        str(entry.cn)
                        if hasattr(entry, "cn") and entry.cn
                        else sam
                    )
                    email = (
                        str(entry.mail)
                        if hasattr(entry, "mail") and entry.mail
                        else None
                    )
                    dn = str(entry.entry_dn)
                    groups = (
                        [str(g) for g in entry.memberOf]
                        if hasattr(entry, "memberOf") and entry.memberOf
                        else []
                    )
                    role = self._map_groups_to_role(groups)

                    # AD ACCOUNTDISABLE flag (bit 1 of userAccountControl).
                    uac_raw = (
                        str(entry.userAccountControl)
                        if hasattr(entry, "userAccountControl")
                        and entry.userAccountControl
                        else "0"
                    )
                    try:
                        uac = int(uac_raw)
                    except ValueError:
                        uac = 0
                    is_active = not bool(uac & 0x0002)

                    local_user = (
                        self.session.query(User)
                        .filter(User.username == sam)
                        .first()
                    )
                    if local_user:
                        local_user.display_name = display_name
                        local_user.email = email
                        local_user.external_id = dn
                        local_user.role = role
                        local_user.is_active = is_active
                        result["updated"] = int(str(result["updated"])) + 1  # type: ignore[arg-type]
                    else:
                        local_user = User(
                            username=sam,
                            display_name=display_name,
                            email=email,
                            auth_provider="ldap",
                            external_id=dn,
                            role=role,
                            is_active=is_active,
                        )
                        self.session.add(local_user)
                        result["created"] = int(str(result["created"])) + 1  # type: ignore[arg-type]

                    result["synced"] = int(str(result["synced"])) + 1  # type: ignore[arg-type]

                except Exception as exc:
                    errors.append(str(exc))

            # Deactivate local LDAP users no longer present in the directory.
            ldap_users_in_db = (
                self.session.query(User)
                .filter(
                    User.auth_provider == "ldap",
                    User.is_active == True,  # noqa: E712
                )
                .all()
            )
            for db_user in ldap_users_in_db:
                if db_user.username not in ldap_usernames:
                    db_user.is_active = False
                    result["deactivated"] = int(str(result["deactivated"])) + 1  # type: ignore[arg-type]

            self.session.commit()
            result["errors"] = errors

        except ImportError:
            cast_errors = list(result.get("errors", []))  # type: ignore[arg-type]
            cast_errors.append("ldap3 library not installed")
            result["errors"] = cast_errors
        except Exception as exc:
            cast_errors = list(result.get("errors", []))  # type: ignore[arg-type]
            cast_errors.append(str(exc))
            result["errors"] = cast_errors

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _map_groups_to_role(self, group_dns: list[str]) -> str:
        """Translate a list of AD group DNs into the highest matching app role.

        The ``ldap_group_mapping_json`` configuration key is expected to be a
        JSON object mapping role names to partial or full group DNs::

            {
                "ADMIN":     "CN=EstimationAdmins,OU=Groups,DC=example,DC=com",
                "APPROVER":  "CN=EstimationApprovers,OU=Groups,DC=example,DC=com",
                "ESTIMATOR": "CN=Estimators,OU=Groups,DC=example,DC=com"
            }

        Matching is case-insensitive and substring-based to tolerate minor DN
        formatting differences.

        Args:
            group_dns: List of distinguished names from the user's
                ``memberOf`` attribute.

        Returns:
            The highest-privilege role the user qualifies for, defaulting to
            ``"VIEWER"`` when no mapping matches.
        """
        mapping_str = self.config.get("ldap_group_mapping_json", "{}")
        try:
            mapping: dict[str, str] = json.loads(mapping_str) if mapping_str else {}
        except (json.JSONDecodeError, TypeError):
            mapping = {}

        for role in ("ADMIN", "APPROVER", "ESTIMATOR", "VIEWER"):
            group_dn = mapping.get(role)
            if group_dn and any(
                group_dn.lower() in g.lower() for g in group_dns
            ):
                return role

        return "VIEWER"
