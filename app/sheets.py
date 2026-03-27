"""
Google Sheets logging for legal receptionist intake sessions.

Uses Google Sheets Python API (service account) on Render,
falls back to npx Google Workspace CLI locally.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime

from app.config import SHEET_TITLE, INTAKE_HEADERS

NPX_PATH = shutil.which("npx") or r"C:\Program Files\nodejs\npx.cmd"
_GWS_AVAILABLE = shutil.which("npx") is not None

# Will be set after first run creates/finds the sheet
_sheet_id = os.environ.get("INTAKE_SHEET_ID", "")


def _use_python_api():
    """Check if we should use the Python Google API client."""
    try:
        from app.google_api import is_available
        return is_available()
    except ImportError:
        return False


def _run_gws(args_list):
    """Run a Google Workspace CLI command and return parsed JSON."""
    if not _GWS_AVAILABLE:
        raise RuntimeError("Google Workspace CLI not available (server deployment)")
    cmd = [NPX_PATH, "@googleworkspace/cli"] + args_list
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, shell=(os.name == "nt")
    )
    if result.returncode != 0:
        raise RuntimeError(f"GWS CLI error: {result.stderr.strip()}")
    output = result.stdout.strip()
    for i, ch in enumerate(output):
        if ch in "{[":
            try:
                return json.loads(output[i:])
            except json.JSONDecodeError:
                continue
    return None


def get_or_create_sheet():
    """Find or create the intake log spreadsheet. Returns sheet ID."""
    global _sheet_id
    if _sheet_id:
        return _sheet_id

    use_api = _use_python_api()

    if use_api:
        from app.google_api import get_sheets_service
        service = get_sheets_service()
        if service:
            # If INTAKE_SHEET_ID is set, use it directly
            env_id = os.environ.get("INTAKE_SHEET_ID", "")
            if env_id:
                _sheet_id = env_id
                return _sheet_id

            # Create new sheet via API
            body = {
                "properties": {"title": SHEET_TITLE},
                "sheets": [{"properties": {"title": "INTAKES"}}],
            }
            result = service.spreadsheets().create(body=body).execute()
            _sheet_id = result["spreadsheetId"]

            # Add headers
            service.spreadsheets().values().update(
                spreadsheetId=_sheet_id,
                range="INTAKES!A1",
                valueInputOption="RAW",
                body={"values": [INTAKE_HEADERS]},
            ).execute()

            print(f"[Sheets] Created new sheet: {_sheet_id}", flush=True)
            return _sheet_id

    if not _GWS_AVAILABLE:
        raise RuntimeError("No Sheets backend available. Set INTAKE_SHEET_ID env var.")

    # Fall back to npx
    result = _run_gws([
        "drive", "files", "list",
        "--params", json.dumps({
            "q": f"name='{SHEET_TITLE}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
            "fields": "files(id,name)",
        }),
    ])

    if result and result.get("files"):
        _sheet_id = result["files"][0]["id"]
        return _sheet_id

    result = _run_gws([
        "sheets", "spreadsheets", "create",
        "--json", json.dumps({
            "properties": {"title": SHEET_TITLE},
            "sheets": [{"properties": {"title": "INTAKES"}}],
        }),
    ])

    _sheet_id = result["spreadsheetId"]

    _run_gws([
        "sheets", "spreadsheets", "values", "update",
        "--params", json.dumps({
            "spreadsheetId": _sheet_id,
            "range": "INTAKES!A1",
            "valueInputOption": "RAW",
        }),
        "--body", json.dumps({"values": [INTAKE_HEADERS]}),
    ])

    return _sheet_id


def log_intake(session_summary):
    """Log a completed intake session to Google Sheets."""
    sheet_id = get_or_create_sheet()

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        session_summary.get("session_id", ""),
        session_summary.get("caller_name", ""),
        session_summary.get("phone", ""),
        session_summary.get("email", ""),
        session_summary.get("practice_area", ""),
        session_summary.get("matter_summary", ""),
        session_summary.get("urgency", ""),
        session_summary.get("opposing_party", ""),
        "YES" if session_summary.get("conflict_flag") else "NO",
        session_summary.get("outcome", ""),
        "",  # Notes
        session_summary.get("how_found", ""),
    ]

    use_api = _use_python_api()

    if use_api:
        from app.google_api import get_sheets_service
        service = get_sheets_service()
        if service:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range="INTAKES!A:M",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            ).execute()
            print(f"[Sheets] Logged intake via API: {session_summary.get('caller_name', '')}", flush=True)
            return sheet_id

    # Fall back to npx
    _run_gws([
        "sheets", "spreadsheets", "values", "append",
        "--params", json.dumps({
            "spreadsheetId": sheet_id,
            "range": "INTAKES!A:M",
            "valueInputOption": "RAW",
            "insertDataOption": "INSERT_ROWS",
        }),
        "--body", json.dumps({"values": [row]}),
    ])

    return sheet_id


def get_intakes(limit=20):
    """Get recent intake records."""
    sheet_id = get_or_create_sheet()

    use_api = _use_python_api()
    rows = []

    if use_api:
        from app.google_api import get_sheets_service
        service = get_sheets_service()
        if service:
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="INTAKES!A:M",
            ).execute()
            rows = result.get("values", [])
    else:
        result = _run_gws([
            "sheets", "spreadsheets", "values", "get",
            "--params", json.dumps({
                "spreadsheetId": sheet_id,
                "range": "INTAKES!A:M",
            }),
        ])
        rows = result.get("values", []) if result else []

    if len(rows) <= 1:
        return []

    headers = rows[0]
    records = []
    for row in rows[1:][-limit:]:
        padded = row + [""] * (len(headers) - len(row))
        records.append(dict(zip(headers, padded)))

    return records
