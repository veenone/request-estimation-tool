# Redmine Integration — Usage Guide

## Overview

The Redmine integration allows **bidirectional sync** between the Estimation Tool and Redmine:

- **Import**: Pull open Redmine issues into the tool as Requests
- **Export**: Push estimation results (hours, feasibility, estimation number) back to Redmine issues as custom field values + journal notes

## Prerequisites in Redmine

1. **REST API enabled** — Redmine admin must enable REST API under *Administration > Settings > API*
2. **API key** — Each user generates theirs under *My Account > API access key*
3. **Custom fields created** (optional, for export) — Create 3 custom fields on issues:
   - "Effort Hours" (float) — receives `grand_total_hours`
   - "Feasibility" (text/list) — receives `feasibility_status` (FEASIBLE/RISKY/CRITICAL)
   - "Estimation Number" (text) — receives `EST-XXX` number
   - Note the numeric ID of each custom field (visible in the URL when editing the field)

## Setup Steps

### Via Web Frontend (Streamlit)

1. Run `streamlit run frontend_web/app.py`
2. Navigate to **Integrations** page (sidebar)
3. In the **Redmine** tab, fill in:

| Field | Example | Description |
|-------|---------|-------------|
| Base URL | `https://redmine.company.com` | Your Redmine instance URL |
| API Key | `a1b2c3d4...` | From *My Account > API access key* |
| Project ID | `my-project` or `5` | Redmine project identifier (slug or numeric ID) |
| Tracker ID | `1` | (Optional) Filter to a specific tracker (e.g., "Feature" = 2) |
| Effort Hours Field ID | `7` | Numeric ID of the custom field for effort hours |
| Feasibility Field ID | `8` | Numeric ID of the custom field for feasibility |
| Estimation Number Field ID | `9` | Numeric ID of the custom field for estimation number |

4. Check **Enable Redmine Integration**
5. Click **Save Redmine Configuration**
6. Click **Test Connection** — should show "Connected as: Your Name"

### Via Desktop Frontend (WinForms)

Same fields are available in the **Integrations** panel in the sidebar.

### Via REST API

```bash
# Save/update configuration
curl -X PUT http://localhost:8000/api/integrations/REDMINE \
  -H "Content-Type: application/json" \
  -d '{
    "base_url": "https://redmine.company.com",
    "api_key": "your-api-key",
    "enabled": true,
    "additional_config": {
      "project_id": "my-project",
      "tracker_id": "1",
      "custom_fields": {
        "effort_hours": 7,
        "feasibility": 8,
        "estimation_number": 9
      }
    }
  }'

# Test connection
curl -X POST http://localhost:8000/api/integrations/REDMINE/test

# Trigger import
curl -X POST http://localhost:8000/api/integrations/REDMINE/sync
```

### Via IPC (Desktop)

```json
{"command": "update_integration", "payload": {"system_name": "REDMINE", "base_url": "...", "api_key": "...", "enabled": true, "additional_config": {"project_id": "my-project"}}}
{"command": "test_integration", "payload": {"system_name": "REDMINE"}}
{"command": "sync_import", "payload": {"system_name": "REDMINE"}}
```

## Workflow

### Import: Redmine Issues → Requests

1. Click **Manual Sync** on the Integrations page (or call the sync API)
2. The adapter fetches all **open** issues from the configured project (optionally filtered by tracker)
3. Each issue is mapped to a Request:
   - `external_id` = Redmine issue ID
   - `title` = issue subject
   - `description` = issue description
   - `requester_name` = issue author name
   - `priority` = mapped from Redmine (Low→LOW, Normal→MEDIUM, High→HIGH, Urgent/Immediate→CRITICAL)
   - `requested_delivery_date` = issue due date
4. Imported requests appear in the **Request Inbox** with source = "REDMINE"
5. You can then create an estimation linked to that request via the wizard

### Export: Estimation → Redmine Issue

After completing an estimation linked to a Redmine-sourced request:

1. The `export_estimation()` method sends a PUT to `/issues/{external_id}.json`
2. It updates the configured custom fields on the Redmine issue:
   - Effort Hours = `grand_total_hours`
   - Feasibility = `feasibility_status`
   - Estimation Number = `estimation_number`
3. It also adds a **journal note** on the issue:
   ```
   Estimation EST-001 completed.
   Total effort: 511.5 hours
   Feasibility: AT_RISK
   ```
4. Optionally, you can upload report attachments (PDF/Word/Excel) to the issue via `upload_attachment()`

### Attach Reports to Redmine Issue

```python
from integrations.redmine_adapter import RedmineAdapter

adapter = RedmineAdapter(config)
with open("report.pdf", "rb") as f:
    result = adapter.upload_attachment(
        issue_id="123",
        filename="estimation_report.pdf",
        content=f.read()
    )
```

## Data Flow Diagram

```
Redmine                          Estimation Tool
┌──────────┐   import_requests   ┌──────────────┐
│  Issues   │ ─────────────────> │   Requests    │
│ (open)    │                    │  (Inbox)      │
└──────────┘                    └──────┬───────┘
                                       │ Link to estimation
                                       v
                                ┌──────────────┐
                                │  Estimation   │
                                │  (Wizard)     │
                                └──────┬───────┘
                                       │ export_estimation
┌──────────┐   PUT /issues/ID    ◄─────┘
│  Issue    │ <──────────────────
│ (updated) │  custom fields +
│           │  journal note
└──────────┘
```

## Troubleshooting

### "Connection failed" on test

- Verify the Base URL is correct and reachable from the machine running the tool
- Ensure the URL does not have a trailing slash
- Check that the API key is valid (try accessing `https://your-redmine/users/current.json` with the key in a browser or curl)
- Confirm REST API is enabled in Redmine admin settings

### No issues imported

- Check that the configured Project ID matches an actual Redmine project (use the URL slug, e.g., `my-project`)
- If using a Tracker ID filter, verify issues exist with that tracker
- Only **open** issues are imported (status not closed/resolved)
- The import fetches up to 100 issues per sync, sorted by most recently updated

### Custom fields not updating on export

- Verify the custom field IDs are correct (check in Redmine under *Administration > Custom fields* — the ID is in the URL)
- Ensure the custom fields are enabled for the issue's tracker and project
- The API key user must have permission to edit issues in that project

### Export mapping note

The Streamlit UI saves custom field IDs as `effort_hours_field_id`, `feasibility_field_id`, and `estimation_number_field_id` in `additional_config`. The adapter reads them from a nested `custom_fields` dict with keys `effort_hours`, `feasibility`, `estimation_number`. If export doesn't update fields, check that the configuration is stored in the correct format.

## Key Files

| File | Purpose |
|------|---------|
| `backend/src/integrations/redmine_adapter.py` | RedmineAdapter class (import, export, upload) |
| `backend/src/integrations/service.py` | Orchestrator (get_adapter, sync_import, sync_export) |
| `backend/src/integrations/base.py` | BaseAdapter ABC, data models (ExternalRequest, SyncResult) |
| `backend/src/api/routes.py` | REST endpoints (`/api/integrations/...`) |
| `backend/src/cli/ipc_handler.py` | IPC commands (get_integrations, update_integration, test_integration, sync_import) |
| `frontend_web/pages/11_integrations.py` | Streamlit config UI |

## Notes

- The import currently fetches up to **100 open issues** per sync, sorted by most recently updated
- The `sync_import` service function updates `last_sync_at` timestamp after each sync
- Duplicate imports are prevented by matching on `external_id` — re-syncing updates existing requests rather than creating duplicates
