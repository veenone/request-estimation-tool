"""External system integrations configuration page.

Configure connections to Redmine, Jira, X-Ray, and Email systems.
Manage authentication credentials, field mappings, and sync operations.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
from sqlalchemy.orm import Session

# Add backend to path
backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend" / "src")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from database.migrations import get_engine
from database.models import IntegrationConfig
from integrations.service import get_integration_status, sync_import, test_integration



st.title("Integrations")
st.markdown("Configure connections to external systems for importing requests and exporting estimations")

engine = get_engine()


# Session state initialization
if "integration_status" not in st.session_state:
    st.session_state.integration_status = {}


def get_integration_config(system_name: str) -> IntegrationConfig:
    """Fetch integration config from database, returning a default if none exists."""
    with Session(engine) as session:
        config = (
            session.query(IntegrationConfig)
            .filter(IntegrationConfig.system_name == system_name)
            .first()
        )
        if config is not None:
            # Expunge so it can be used outside the session
            session.expunge(config)
            return config

    # Return a detached default so callers never get None
    return IntegrationConfig(
        system_name=system_name,
        enabled=False,
        base_url=None,
        api_key=None,
        username=None,
        additional_config_json=None,
        last_sync_at=None,
    )


def save_integration_config(
    system_name: str,
    base_url: str,
    api_key: str,
    username: str,
    additional_config: dict,
    enabled: bool,
) -> bool:
    """Save or update integration configuration."""
    try:
        with Session(engine) as session:
            config = (
                session.query(IntegrationConfig)
                .filter(IntegrationConfig.system_name == system_name)
                .first()
            )

            if config:
                config.base_url = base_url if base_url else None
                config.api_key = api_key if api_key else None
                config.username = username if username else None
                config.additional_config_json = json.dumps(additional_config)
                config.enabled = enabled
            else:
                config = IntegrationConfig(
                    system_name=system_name,
                    base_url=base_url if base_url else None,
                    api_key=api_key if api_key else None,
                    username=username if username else None,
                    additional_config_json=json.dumps(additional_config),
                    enabled=enabled,
                )
                session.add(config)

            session.commit()
            return True
    except Exception as e:
        st.error(f"Error saving configuration: {str(e)}")
        return False


def format_last_sync(last_sync_at: datetime | None) -> str:
    """Format last sync datetime."""
    if not last_sync_at:
        return "Never"
    return last_sync_at.strftime("%Y-%m-%d %H:%M:%S")


def render_redmine_tab():
    """Render Redmine integration tab."""
    st.subheader("Redmine Configuration")

    config = get_integration_config("REDMINE")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Connection Settings**")

        base_url = st.text_input(
            "Base URL",
            value=config.base_url or "",
            placeholder="https://redmine.example.com",
            key="redmine_base_url",
            help="Redmine server URL",
        )

        api_key = st.text_input(
            "API Key",
            value=config.api_key or "",
            type="password",
            placeholder="Your Redmine API key",
            key="redmine_api_key",
            help="Generate from Redmine user account settings",
        )

    with col2:
        st.write("**Additional Settings**")

        # Parse existing additional config
        additional_config = {}
        if config and config.additional_config_json:
            try:
                additional_config = json.loads(config.additional_config_json)
            except json.JSONDecodeError:
                additional_config = {}

        project_id = st.text_input(
            "Project ID",
            value=additional_config.get("project_id", ""),
            placeholder="e.g., 1",
            key="redmine_project_id",
            help="Redmine project identifier",
        )

        tracker_id = st.text_input(
            "Tracker ID",
            value=additional_config.get("tracker_id", ""),
            placeholder="e.g., 1",
            key="redmine_tracker_id",
            help="Redmine tracker identifier for feature requests",
        )

    st.divider()

    st.write("**Field Mappings**")
    col1, col2, col3 = st.columns(3)

    with col1:
        effort_field = st.text_input(
            "Effort Hours Field ID",
            value=additional_config.get("effort_hours_field_id", ""),
            placeholder="Custom field ID or 'estimated_hours'",
            key="redmine_effort_field",
            help="Custom field ID for effort hours, or enter 'estimated_hours' to use Redmine's built-in Estimated Hours field",
        )

    with col2:
        feasibility_field = st.text_input(
            "Feasibility Field ID",
            value=additional_config.get("feasibility_field_id", ""),
            placeholder="Custom field ID",
            key="redmine_feasibility_field",
            help="Custom field ID for feasibility status",
        )

    with col3:
        estimation_field = st.text_input(
            "Estimation Number Field ID",
            value=additional_config.get("estimation_number_field_id", ""),
            placeholder="Custom field ID",
            key="redmine_estimation_field",
            help="Custom field ID for estimation number",
        )

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    enabled = st.checkbox(
        "Enable Redmine Integration",
        value=config.enabled if config else False,
        key="redmine_enabled",
    )

    # Status display
    with col2:
        if config and config.last_sync_at:
            st.caption(f"Last sync: {format_last_sync(config.last_sync_at)}")

    # Action buttons
    with col3:
        if st.button("Test Connection", key="redmine_test"):
            with st.spinner("Testing connection..."):
                with Session(engine) as session:
                    result = test_integration("REDMINE", session)
                if result.success:
                    st.success(f"Connection successful! {result.message}")
                else:
                    st.error(f"Connection failed: {result.message}")

    with col4:
        if st.button("Manual Sync", key="redmine_sync"):
            with st.spinner("Syncing from Redmine..."):
                with Session(engine) as session:
                    result = sync_import("REDMINE", session)
                if result.status.value == "SUCCESS":
                    st.cache_data.clear()
                    st.success(
                        f"Sync complete: {result.items_created} created, "
                        f"{result.items_updated} updated"
                    )
                elif result.status.value == "PARTIAL":
                    st.cache_data.clear()
                    st.warning(
                        f"Sync partial: {result.items_created} created, "
                        f"{result.items_updated} updated, "
                        f"{result.items_failed} failed"
                    )
                else:
                    st.error(f"Sync failed: {', '.join(result.errors)}")

    st.divider()

    # Save button
    if st.button("Save Redmine Configuration", type="primary", use_container_width=True):
        additional_config = {
            "project_id": project_id,
            "tracker_id": tracker_id,
            "effort_hours_field_id": effort_field,
            "feasibility_field_id": feasibility_field,
            "estimation_number_field_id": estimation_field,
        }

        if save_integration_config(
            "REDMINE",
            base_url,
            api_key,
            "",
            additional_config,
            enabled,
        ):
            st.success("Redmine configuration saved successfully!")
            st.rerun()


def render_jira_tab():
    """Render Jira integration tab."""
    st.subheader("Jira Configuration")

    config = get_integration_config("JIRA")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Connection Settings**")

        base_url = st.text_input(
            "Base URL",
            value=config.base_url or "",
            placeholder="https://jira.example.com",
            key="jira_base_url",
            help="Jira server URL",
        )

        api_key = st.text_input(
            "API Key",
            value=config.api_key or "",
            type="password",
            placeholder="Your Jira API key",
            key="jira_api_key",
            help="Generate from Jira account settings",
        )

        username = st.text_input(
            "Username",
            value=config.username or "",
            placeholder="Jira username",
            key="jira_username",
            help="Jira account username",
        )

    with col2:
        st.write("**Additional Settings**")

        # Parse existing additional config
        additional_config = {}
        if config and config.additional_config_json:
            try:
                additional_config = json.loads(config.additional_config_json)
            except json.JSONDecodeError:
                additional_config = {}

        jql_filter = st.text_area(
            "JQL Filter",
            value=additional_config.get("jql_filter", ""),
            placeholder='e.g., type = "Feature Request" AND status = "Open"',
            key="jira_jql_filter",
            help="JQL query to filter issues for import",
        )

        project_key = st.text_input(
            "Project Key",
            value=additional_config.get("project_key", ""),
            placeholder="e.g., PROJ",
            key="jira_project_key",
            help="Jira project key",
        )

    st.divider()

    st.write("**Deployment Settings**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        is_cloud = st.checkbox(
            "Jira Cloud",
            value=additional_config.get("is_cloud", False),
            key="jira_is_cloud",
            help="Check if using Jira Cloud. Uncheck for Server or Data Center.",
        )

    with col2:
        auth_mode = st.selectbox(
            "Auth Mode",
            options=["auto", "basic", "pat"],
            index=["auto", "basic", "pat"].index(
                additional_config.get("auth_mode", "auto")
            ) if additional_config.get("auth_mode", "auto") in ("auto", "basic", "pat") else 0,
            key="jira_auth_mode",
            help="'pat' = Personal Access Token (DC/Server), 'basic' = username+password, 'auto' = detect from fields",
        )

    with col3:
        issue_type = st.text_input(
            "Issue Type",
            value=additional_config.get("issue_type", ""),
            placeholder="e.g., Story",
            key="jira_issue_type",
            help="Issue type for feature requests",
        )

    with col4:
        ssl_verify = st.checkbox(
            "Verify SSL",
            value=additional_config.get("ssl_verify", True),
            key="jira_ssl_verify",
            help="Uncheck for DC instances with self-signed certificates",
        )

    st.divider()

    st.write("**Field Mappings**")
    col1, col2, col3 = st.columns(3)

    with col1:
        effort_field = st.text_input(
            "Effort Hours Custom Field",
            value=additional_config.get("effort_hours_field", ""),
            placeholder="customfield_10000 or 'originalEstimate'",
            key="jira_effort_field",
            help="Custom field ID for effort hours, or enter 'originalEstimate' to use Jira's built-in time tracking field",
        )

    with col2:
        feasibility_field = st.text_input(
            "Feasibility Custom Field",
            value=additional_config.get("feasibility_field", ""),
            placeholder="customfield_10001",
            key="jira_feasibility_field",
            help="Custom field name or ID for feasibility",
        )

    with col3:
        estimation_field = st.text_input(
            "Estimation Number Custom Field",
            value=additional_config.get("estimation_number_field", ""),
            placeholder="customfield_10002",
            key="jira_estimation_field",
            help="Custom field name or ID for estimation number",
        )

    st.divider()

    st.write("**X-Ray Integration**")
    col1, col2 = st.columns(2)

    with col1:
        xray_enabled = st.checkbox(
            "Enable X-Ray Integration",
            value=additional_config.get("xray_enabled", False),
            key="jira_xray_enabled",
            help="Enable test result sync with X-Ray",
        )

    with col2:
        xray_project_key = st.text_input(
            "X-Ray Project Key",
            value=additional_config.get("xray_project_key", ""),
            placeholder="e.g., XRAY",
            key="jira_xray_project_key",
            help="X-Ray project key in Jira",
        )

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    enabled = st.checkbox(
        "Enable Jira Integration",
        value=config.enabled if config else False,
        key="jira_enabled",
    )

    with col2:
        if config and config.last_sync_at:
            st.caption(f"Last sync: {format_last_sync(config.last_sync_at)}")

    with col3:
        if st.button("Test Connection", key="jira_test"):
            with st.spinner("Testing connection..."):
                with Session(engine) as session:
                    result = test_integration("JIRA", session)
                if result.success:
                    st.success(f"Connection successful! {result.message}")
                else:
                    st.error(f"Connection failed: {result.message}")

    with col4:
        if st.button("Manual Sync", key="jira_sync"):
            with st.spinner("Syncing from Jira..."):
                with Session(engine) as session:
                    result = sync_import("JIRA", session)
                if result.status.value == "SUCCESS":
                    st.cache_data.clear()
                    st.success(
                        f"Sync complete: {result.items_created} created, "
                        f"{result.items_updated} updated"
                    )
                elif result.status.value == "PARTIAL":
                    st.cache_data.clear()
                    st.warning(
                        f"Sync partial: {result.items_created} created, "
                        f"{result.items_updated} updated, "
                        f"{result.items_failed} failed"
                    )
                else:
                    st.error(f"Sync failed: {', '.join(result.errors)}")

    st.divider()

    # Save button
    if st.button("Save Jira Configuration", type="primary", use_container_width=True):
        additional_config = {
            "jql_filter": jql_filter,
            "project_key": project_key,
            "issue_type": issue_type,
            "is_cloud": is_cloud,
            "auth_mode": auth_mode,
            "ssl_verify": ssl_verify,
            "effort_hours_field": effort_field,
            "feasibility_field": feasibility_field,
            "estimation_number_field": estimation_field,
            "xray_enabled": xray_enabled,
            "xray_project_key": xray_project_key,
        }

        if save_integration_config(
            "JIRA",
            base_url,
            api_key,
            username,
            additional_config,
            enabled,
        ):
            st.success("Jira configuration saved successfully!")
            st.rerun()


def render_email_tab():
    """Render Email integration tab."""
    st.subheader("Email Configuration")

    config = get_integration_config("EMAIL")

    # Parse existing additional config
    additional_config = {}
    if config and config.additional_config_json:
        try:
            additional_config = json.loads(config.additional_config_json)
        except json.JSONDecodeError:
            additional_config = {}

    col1, col2 = st.columns(2)

    with col1:
        st.write("**SMTP Settings**")

        smtp_host = st.text_input(
            "SMTP Host",
            value=additional_config.get("smtp_host", ""),
            placeholder="smtp.gmail.com",
            key="email_smtp_host",
            help="SMTP server hostname",
        )

        smtp_port = st.number_input(
            "SMTP Port",
            value=int(additional_config.get("smtp_port", 587)),
            min_value=1,
            max_value=65535,
            key="email_smtp_port",
            help="SMTP server port (commonly 587 for TLS, 465 for SSL)",
        )

        smtp_use_tls = st.checkbox(
            "Use TLS",
            value=additional_config.get("smtp_use_tls", True),
            key="email_smtp_use_tls",
            help="Enable TLS encryption for SMTP",
        )

    with col2:
        st.write("**Authentication**")

        username = st.text_input(
            "SMTP Username",
            value=config.username or "",
            placeholder="your-email@example.com",
            key="email_username",
            help="SMTP authentication username",
        )

        api_key = st.text_input(
            "SMTP Password",
            value=config.api_key or "",
            type="password",
            placeholder="Your email password or app password",
            key="email_password",
            help="SMTP authentication password or app-specific password",
        )

    st.divider()

    st.write("**Sender Settings**")
    col1, col2 = st.columns(2)

    with col1:
        sender_email = st.text_input(
            "Sender Email",
            value=additional_config.get("sender_email", ""),
            placeholder="noreply@example.com",
            key="email_sender_email",
            help="Email address to send from",
        )

    with col2:
        sender_name = st.text_input(
            "Sender Name",
            value=additional_config.get("sender_name", ""),
            placeholder="Estimation Tool",
            key="email_sender_name",
            help="Display name for sender",
        )

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    enabled = st.checkbox(
        "Enable Email Integration",
        value=config.enabled if config else False,
        key="email_enabled",
    )

    with col2:
        if config and config.last_sync_at:
            st.caption(f"Last sync: {format_last_sync(config.last_sync_at)}")

    with col3:
        if st.button("Test Connection", key="email_test"):
            with st.spinner("Testing email connection..."):
                with Session(engine) as session:
                    result = test_integration("EMAIL", session)
                if result.success:
                    st.success(f"Connection successful! {result.message}")
                else:
                    st.error(f"Connection failed: {result.message}")

    with col4:
        if st.button("Send Test Email", key="email_send_test"):
            st.info("Test email functionality would be triggered here.")

    st.divider()

    # Save button
    if st.button("Save Email Configuration", type="primary", use_container_width=True):
        additional_config = {
            "smtp_host": smtp_host,
            "smtp_port": int(smtp_port),
            "smtp_use_tls": smtp_use_tls,
            "sender_email": sender_email,
            "sender_name": sender_name,
        }

        if save_integration_config(
            "EMAIL",
            "",
            api_key,
            username,
            additional_config,
            enabled,
        ):
            st.success("Email configuration saved successfully!")
            st.rerun()


def render_integration_status():
    """Render overview of all integration statuses."""
    st.subheader("Integration Status Overview")

    with st.spinner("Loading integration status..."):
        with Session(engine) as session:
            statuses = get_integration_status(session)

    if statuses:
        status_data = []
        for status in statuses:
            status_data.append({
                "System": status["system_name"],
                "Enabled": "Yes" if status["enabled"] else "No",
                "Configured": "Yes" if status["has_api_key"] else "No",
                "Last Sync": status["last_sync_at"] or "Never",
            })

        # Display as table
        import pandas as pd

        df = pd.DataFrame(status_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No integrations configured yet.")

    st.divider()


# Main UI
render_integration_status()

# Tabs for each integration
tab1, tab2, tab3 = st.tabs(["Redmine", "Jira", "Email"])

with tab1:
    render_redmine_tab()

with tab2:
    render_jira_tab()

with tab3:
    render_email_tab()

# Information section
st.divider()
st.subheader("Integration Help")

with st.expander("Redmine Setup Instructions"):
    st.markdown("""
    **1. Get API Key:**
    - Log in to your Redmine instance
    - Go to Account settings (your username)
    - Find "API access key" section
    - Copy the API key

    **2. Find Custom Field IDs:**
    - Go to Administration > Custom fields
    - Identify the fields you want to map
    - Note their IDs from the URL or field list

    **3. Configure Project Settings:**
    - Note your Redmine project ID
    - Identify the tracker ID for feature requests
    - These are typically visible in the project settings

    **4. Test the Connection:**
    - Click "Test Connection" to verify configuration
    - Click "Manual Sync" to import requests
    """)

with st.expander("Jira Setup Instructions"):
    st.markdown("""
    **1. Authentication:**
    - **Cloud**: Go to *Account settings > Security > API tokens > Create token*. Enter your email as Username and the token as API Key. Check "Jira Cloud".
    - **Data Center / Server (Basic Auth)**: Enter your Jira username and password. Uncheck "Jira Cloud". Set Auth Mode to "basic".
    - **Data Center / Server (PAT)**: Go to *Profile > Personal Access Tokens > Create token*. Leave Username empty, paste the token as API Key. Set Auth Mode to "pat".

    **2. SSL Certificates (Data Center):**
    - If your DC instance uses a self-signed certificate, uncheck "Verify SSL"

    **3. Find Custom Field IDs:**
    - Go to Jira Settings > Issues > Custom fields
    - The field ID appears as "customfield_XXXXX"
    - Note the IDs for fields you want to map
    - Or enter `originalEstimate` for the built-in time tracking field

    **4. Configure JQL Filter:**
    - Use a JQL query to filter issues for import
    - Example: `type = "Story" AND status = "To Do"`

    **5. X-Ray Integration:**
    - Optional: Enable X-Ray for test result tracking
    - Requires X-Ray for Jira plugin installed

    **6. Test the Connection:**
    - Click "Test Connection" to verify configuration
    - It will show the deployment type (Cloud / Server / Data Center) and version
    - Click "Manual Sync" to import requests
    """)

with st.expander("Email Setup Instructions"):
    st.markdown("""
    **1. SMTP Configuration:**
    - Gmail: smtp.gmail.com:587 (TLS enabled)
    - Office 365: smtp.office365.com:587 (TLS enabled)
    - Other providers: Check your email provider's SMTP settings

    **2. Authentication:**
    - For Gmail: Use an App Password (not your regular password)
    - For Office 365: Use your email password or app password
    - Create app-specific passwords in account security settings

    **3. Sender Settings:**
    - Sender Email: Should match your SMTP username or authorized alias
    - Sender Name: Display name for email notifications

    **4. Test Email:**
    - Click "Test Connection" to verify SMTP settings
    - Click "Send Test Email" to receive a test message

    **Common Issues:**
    - "Authentication failed": Check username/password and SMTP settings
    - "Connection refused": Verify SMTP host and port are correct
    - "TLS errors": Try toggling TLS on/off based on your provider
    """)
