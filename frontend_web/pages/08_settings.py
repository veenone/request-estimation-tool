"""Global configuration settings page.

Edit system-wide configuration parameters.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

# Add backend to path
backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend" / "src")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from database.migrations import get_engine
from database.models import Configuration

st.title("⚙️ Settings")
st.markdown("Configure global system parameters")

engine = get_engine()

# Default configuration keys with descriptions and types
DEFAULT_CONFIG = {
    "leader_effort_ratio": {
        "description": "Ratio of test leader effort to tester effort (0.0-1.0)",
        "type": "float",
        "default": "0.15",
        "min": 0.0,
        "max": 1.0,
    },
    "pr_fix_base_hours": {
        "description": "Base hours for PR fix tasks",
        "type": "float",
        "default": "2.0",
        "min": 0.5,
        "max": 20.0,
    },
    "new_feature_study_hours": {
        "description": "Hours allocated for studying new features",
        "type": "float",
        "default": "8.0",
        "min": 0.0,
        "max": 40.0,
    },
    "working_hours_per_day": {
        "description": "Standard working hours per day",
        "type": "float",
        "default": "7.0",
        "min": 1.0,
        "max": 12.0,
    },
    "buffer_percentage": {
        "description": "Buffer percentage for estimates (0-100)",
        "type": "float",
        "default": "15.0",
        "min": 0.0,
        "max": 100.0,
    },
    "estimation_number_prefix": {
        "description": "Prefix for estimation numbers (e.g., 'EST')",
        "type": "string",
        "default": "EST",
    },
}


@st.cache_data(ttl=60)
def get_config_data():
    """Fetch all configuration from the database."""
    with Session(engine) as session:
        configs = session.query(Configuration).all()
        config_dict = {c.key: (c.value, c.description) for c in configs}
        return config_dict


def get_all_config_items():
    """Get all config items with defaults filled in."""
    current_config = get_config_data()
    items = {}

    for key, config in DEFAULT_CONFIG.items():
        if key in current_config:
            value, description = current_config[key]
        else:
            value = config["default"]
            description = None

        items[key] = {
            "value": value,
            "description": description or config["description"],
            "type": config["type"],
            **{k: v for k, v in config.items() if k not in ["description", "type", "default"]},
        }

    return items


def update_config(updates: dict[str, str]) -> bool:
    """Update configuration values."""
    try:
        with Session(engine) as session:
            for key, value in updates.items():
                config = session.query(Configuration).filter(
                    Configuration.key == key
                ).first()

                description = DEFAULT_CONFIG.get(key, {}).get("description", "")

                if config:
                    config.value = value
                else:
                    config = Configuration(
                        key=key,
                        value=value,
                        description=description,
                    )
                    session.add(config)

            session.commit()
            return True
    except Exception as e:
        st.error(f"Error updating configuration: {str(e)}")
        return False


def reset_to_defaults() -> bool:
    """Reset all configuration to default values."""
    try:
        updates = {}
        for key, config in DEFAULT_CONFIG.items():
            updates[key] = config["default"]
        return update_config(updates)
    except Exception as e:
        st.error(f"Error resetting configuration: {str(e)}")
        return False


# Main UI
col1, col2, col3 = st.columns([2, 1, 1])

with col2:
    if st.button("Reset to Defaults", use_container_width=True):
        st.session_state["show_reset_confirm"] = True

with col3:
    st.write("")  # Spacer
    st.write("")  # Spacer

# Get current configuration
config_items = get_all_config_items()

st.subheader("Configuration Parameters")

# Display current configuration in a table first
st.write("**Current Settings:**")

table_data = []
for key, item in config_items.items():
    table_data.append({
        "Key": key,
        "Value": item["value"],
        "Type": item["type"],
        "Description": item["description"],
    })

df_config = pd.DataFrame(table_data)
st.dataframe(df_config, use_container_width=True, hide_index=True)

st.divider()

# Settings form
st.write("**Edit Settings:**")

with st.form("settings_form"):
    updates = {}

    # Organize by category
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Estimation Parameters**")

        # Leader effort ratio
        leader_ratio = st.number_input(
            "Leader Effort Ratio",
            min_value=0.0,
            max_value=1.0,
            value=float(config_items["leader_effort_ratio"]["value"]),
            step=0.05,
            help=config_items["leader_effort_ratio"]["description"],
        )
        updates["leader_effort_ratio"] = str(leader_ratio)

        # PR fix base hours
        pr_fix_hours = st.number_input(
            "PR Fix Base Hours",
            min_value=0.5,
            max_value=20.0,
            value=float(config_items["pr_fix_base_hours"]["value"]),
            step=0.5,
            help=config_items["pr_fix_base_hours"]["description"],
        )
        updates["pr_fix_base_hours"] = str(pr_fix_hours)

        # New feature study hours
        study_hours = st.number_input(
            "New Feature Study Hours",
            min_value=0.0,
            max_value=40.0,
            value=float(config_items["new_feature_study_hours"]["value"]),
            step=0.5,
            help=config_items["new_feature_study_hours"]["description"],
        )
        updates["new_feature_study_hours"] = str(study_hours)

    with col2:
        st.write("**Time & Buffer Settings**")

        # Working hours per day
        working_hours = st.number_input(
            "Working Hours per Day",
            min_value=1.0,
            max_value=12.0,
            value=float(config_items["working_hours_per_day"]["value"]),
            step=0.5,
            help=config_items["working_hours_per_day"]["description"],
        )
        updates["working_hours_per_day"] = str(working_hours)

        # Buffer percentage
        buffer = st.number_input(
            "Buffer Percentage",
            min_value=0.0,
            max_value=100.0,
            value=float(config_items["buffer_percentage"]["value"]),
            step=1.0,
            help=config_items["buffer_percentage"]["description"],
        )
        updates["buffer_percentage"] = str(buffer)

    st.divider()
    st.write("**Naming Prefixes**")

    col_a, col_b = st.columns(2)
    with col_a:
        est_prefix = st.text_input(
            "Estimation Number Prefix",
            value=config_items["estimation_number_prefix"]["value"],
            help=config_items["estimation_number_prefix"]["description"],
        )
        updates["estimation_number_prefix"] = est_prefix

    st.divider()

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.form_submit_button("Save Settings", type="primary"):
            if update_config(updates):
                st.success("Settings saved successfully!")
                st.cache_data.clear()
                st.rerun()

    with col2:
        if st.form_submit_button("Cancel"):
            st.rerun()

# Reset confirmation dialog
if st.session_state.get("show_reset_confirm"):
    st.divider()
    st.warning(
        "⚠️ This will reset all settings to their default values. "
        "This action cannot be undone."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Reset to Defaults", type="primary", key="confirm_reset"):
            if reset_to_defaults():
                st.success("Settings reset to defaults!")
                st.cache_data.clear()
                st.session_state["show_reset_confirm"] = False
                st.rerun()

    with col2:
        if st.button("Cancel", key="cancel_reset"):
            st.session_state["show_reset_confirm"] = False
            st.rerun()

# Configuration info section
st.divider()
st.subheader("Configuration Information")

info_col1, info_col2 = st.columns(2)

with info_col1:
    st.write("**Key Descriptions:**")

    for key, item in config_items.items():
        with st.expander(f"🔑 {key}"):
            st.write(f"**Description:** {item['description']}")
            st.write(f"**Type:** {item['type']}")
            st.write(f"**Current Value:** `{item['value']}`")
            if item["type"] == "float":
                st.write(f"**Range:** {item.get('min', 'N/A')} - {item.get('max', 'N/A')}")

with info_col2:
    st.write("**Usage Guidelines:**")
    st.info(
        """
        **Leader Effort Ratio:** Determines how much time test leaders spend on tasks.
        Higher values mean more leader involvement.

        **PR Fix Base Hours:** Base effort for each PR fix task. Adjusted based on complexity.

        **Study Hours:** Time allocated for team members to study new features before testing.

        **Working Hours:** Standard daily working hours. Used for capacity calculations.

        **Buffer %:** Safety margin added to estimates to account for uncertainties.

        **Number Prefixes:** Used to generate unique identifiers for estimations and requests.
        """
    )

# Import/Export section
st.divider()
st.subheader("Export Configuration")

if st.button("Export Current Configuration as JSON"):
    import json

    config_data = get_config_data()
    export_data = {}
    for key, item in config_items.items():
        export_data[key] = {
            "value": item["value"],
            "description": item["description"],
        }

    json_str = json.dumps(export_data, indent=2)
    st.download_button(
        label="Download Configuration JSON",
        data=json_str,
        file_name="estimation_tool_config.json",
        mime="application/json",
    )
