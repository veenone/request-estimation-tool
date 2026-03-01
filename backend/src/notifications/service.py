"""Notification service for sending email alerts on key events."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from ..database.models import Configuration
from . import templates


class NotificationService:
    """Sends email notifications for estimation events.

    Reads SMTP settings from the ``configuration`` table at call time so
    that changes made through the UI take effect without restarting the
    application.

    Configuration keys consumed:
        - ``smtp_host``      – SMTP server hostname (required to enable sending)
        - ``smtp_port``      – SMTP port, defaults to ``587``
        - ``smtp_user``      – Login username
        - ``smtp_password``  – Login password
        - ``smtp_from``      – Sender address; falls back to ``smtp_user``
        - ``smtp_tls``       – ``"true"`` / ``"false"``; defaults to ``"true"``
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_config(self, key: str, default: str = "") -> str:
        cfg = (
            self.session.query(Configuration)
            .filter(Configuration.key == key)
            .first()
        )
        return cfg.value if cfg else default

    @property
    def is_configured(self) -> bool:
        """Return True when an SMTP host has been set in configuration."""
        return bool(self._get_config("smtp_host"))

    def _send_email(
        self, to_emails: list[str], subject: str, html_body: str
    ) -> bool:
        """Construct and deliver an HTML email via SMTP.

        Returns True on success, False on any failure (misconfiguration,
        network error, auth error, etc.).  Errors are silently swallowed
        so that a notification failure never breaks a business operation.
        """
        if not self.is_configured:
            return False

        smtp_host = self._get_config("smtp_host")
        smtp_port = int(self._get_config("smtp_port", "587"))
        smtp_user = self._get_config("smtp_user")
        smtp_password = self._get_config("smtp_password")
        smtp_from = self._get_config("smtp_from", smtp_user)
        smtp_tls = self._get_config("smtp_tls", "true").lower() == "true"

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = smtp_from
            msg["To"] = ", ".join(to_emails)
            msg.attach(MIMEText(html_body, "html"))

            server = smtplib.SMTP(smtp_host, smtp_port)
            if smtp_tls:
                server.starttls()

            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            server.sendmail(smtp_from, to_emails, msg.as_string())
            server.quit()
            return True
        except Exception:
            return False

    def _get_admin_emails(self) -> list[str]:
        """Return email addresses of all active ADMIN users."""
        from ..auth.models import User  # deferred to avoid circular imports

        admins = (
            self.session.query(User)
            .filter(
                User.role == "ADMIN",
                User.is_active == True,  # noqa: E712
                User.email.isnot(None),
            )
            .all()
        )
        return [a.email for a in admins if a.email]

    def _get_user_email(self, user_id: int | None) -> list[str]:
        """Return a single-element list with the user's email, or empty."""
        if not user_id:
            return []
        from ..auth.models import User  # deferred to avoid circular imports

        user = self.session.get(User, user_id)
        return [user.email] if user and user.email else []

    # ------------------------------------------------------------------
    # Public notification methods
    # ------------------------------------------------------------------

    def notify_estimation_status_changed(
        self,
        estimation_number: str,
        project_name: str,
        old_status: str,
        new_status: str,
        changed_by: str,
        grand_total_hours: float = 0,
        creator_user_id: int | None = None,
        assigned_user_id: int | None = None,
    ) -> bool:
        """Notify creator, assignee, and (on FINAL) all admins of a status change.

        Args:
            estimation_number: Human-readable estimation identifier.
            project_name:      Display name of the project.
            old_status:        Previous status string.
            new_status:        Incoming status string.
            changed_by:        Display name of the actor making the change.
            grand_total_hours: Calculated total hours for the estimation.
            creator_user_id:   PK of the user who created the estimation.
            assigned_user_id:  PK of the currently assigned user.

        Returns:
            True if the email was dispatched successfully, False otherwise.
        """
        recipients: set[str] = set()
        recipients.update(self._get_user_email(creator_user_id))
        recipients.update(self._get_user_email(assigned_user_id))
        if new_status == "FINAL":
            recipients.update(self._get_admin_emails())

        if not recipients:
            return False

        subject, body = templates.estimation_status_changed(
            estimation_number,
            project_name,
            old_status,
            new_status,
            changed_by,
            grand_total_hours,
        )
        return self._send_email(list(recipients), subject, body)

    def notify_user_assigned(
        self,
        estimation_number: str,
        project_name: str,
        assignee_user_id: int,
        assigned_by: str,
    ) -> bool:
        """Notify a user that they have been assigned to an estimation.

        Args:
            estimation_number: Human-readable estimation identifier.
            project_name:      Display name of the project.
            assignee_user_id:  PK of the user being assigned.
            assigned_by:       Display name of the actor making the assignment.

        Returns:
            True if the email was dispatched successfully, False otherwise.
        """
        emails = self._get_user_email(assignee_user_id)
        if not emails:
            return False

        from ..auth.models import User  # deferred to avoid circular imports

        assignee = self.session.get(User, assignee_user_id)
        assignee_name = assignee.display_name if assignee else "User"

        subject, body = templates.user_assigned(
            estimation_number, project_name, assignee_name, assigned_by
        )
        return self._send_email(emails, subject, body)

    def notify_request_imported(
        self,
        request_number: str,
        title: str,
        source: str,
        requester_name: str,
    ) -> bool:
        """Notify all admin users that a new request has been imported.

        Args:
            request_number: Identifier from the external system.
            title:          Short description of the request.
            source:         Integration source (e.g. "Redmine", "JIRA").
            requester_name: Name of the person who raised the request.

        Returns:
            True if the email was dispatched successfully, False otherwise.
        """
        recipients = self._get_admin_emails()
        if not recipients:
            return False

        subject, body = templates.request_imported(
            request_number, title, source, requester_name
        )
        return self._send_email(recipients, subject, body)

    def notify_deadline_approaching(
        self,
        estimation_number: str,
        project_name: str,
        delivery_date: str,
        days_remaining: int,
        creator_user_id: int | None = None,
        assigned_user_id: int | None = None,
    ) -> bool:
        """Notify creator and assignee that a delivery deadline is near.

        Args:
            estimation_number: Human-readable estimation identifier.
            project_name:      Display name of the project.
            delivery_date:     ISO-8601 date string of the deadline.
            days_remaining:    Calendar days until the deadline.
            creator_user_id:   PK of the user who created the estimation.
            assigned_user_id:  PK of the currently assigned user.

        Returns:
            True if the email was dispatched successfully, False otherwise.
        """
        recipients: set[str] = set()
        recipients.update(self._get_user_email(creator_user_id))
        recipients.update(self._get_user_email(assigned_user_id))

        if not recipients:
            return False

        subject, body = templates.deadline_approaching(
            estimation_number, project_name, delivery_date, days_remaining
        )
        return self._send_email(list(recipients), subject, body)
