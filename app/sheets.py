"""
Google Sheets logging for Ledger.AI Onboarding Assessments.

Uses Google Sheets Python API (OAuth2) on Render,
falls back to npx Google Workspace CLI locally.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime

from app.config import SHEET_TITLE, SHEET_TAB, INTAKE_HEADERS

NPX_PATH = shutil.which("npx") or r"C:\Program Files\nodejs\npx.cmd"
_GWS_AVAILABLE = shutil.which("npx") is not None

_sheet_id = os.environ.get("INTAKE_SHEET_ID", "")


def _use_python_api():
    try:
        from app.google_api import is_available
        return is_available()
    except ImportError:
        return False


def _run_gws(args_list):
    if not _GWS_AVAILABLE:
        raise RuntimeError("Google Workspace CLI not available")
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
    global _sheet_id
    if _sheet_id:
        return _sheet_id

    use_api = _use_python_api()

    if use_api:
        from app.google_api import get_sheets_service
        service = get_sheets_service()
        if service:
            env_id = os.environ.get("INTAKE_SHEET_ID", "")
            if env_id:
                _sheet_id = env_id
                return _sheet_id

            body = {
                "properties": {"title": SHEET_TITLE},
                "sheets": [{"properties": {"title": SHEET_TAB}}],
            }
            result = service.spreadsheets().create(body=body).execute()
            _sheet_id = result["spreadsheetId"]

            service.spreadsheets().values().update(
                spreadsheetId=_sheet_id,
                range=f"{SHEET_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [INTAKE_HEADERS]},
            ).execute()

            print(f"[Sheets] Created new sheet: {_sheet_id}", flush=True)
            return _sheet_id

    if not _GWS_AVAILABLE:
        raise RuntimeError("No Sheets backend available. Set INTAKE_SHEET_ID env var.")

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
            "sheets": [{"properties": {"title": SHEET_TAB}}],
        }),
    ])

    _sheet_id = result["spreadsheetId"]

    _run_gws([
        "sheets", "spreadsheets", "values", "update",
        "--params", json.dumps({
            "spreadsheetId": _sheet_id,
            "range": f"{SHEET_TAB}!A1",
            "valueInputOption": "RAW",
        }),
        "--body", json.dumps({"values": [INTAKE_HEADERS]}),
    ])

    return _sheet_id


def log_assessment(data):
    """Log a completed assessment to Google Sheets."""
    sheet_id = get_or_create_sheet()

    tools_str = ", ".join(data.get("ai_tools", []))

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        data.get("name", ""),
        data.get("email", ""),
        data.get("company", ""),
        str(data.get("score", "")),
        data.get("level", ""),
        data.get("industry", ""),
        data.get("team_size", ""),
        tools_str,
        data.get("pain_point", ""),
        data.get("ai_goal", ""),
        "YES" if data.get("booked") else "NO",
        data.get("insight", ""),
    ]

    col_range = f"{SHEET_TAB}!A:{chr(64 + len(INTAKE_HEADERS))}"

    use_api = _use_python_api()

    if use_api:
        from app.google_api import get_sheets_service
        service = get_sheets_service()
        if service:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=col_range,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            ).execute()
            print(f"[Sheets] Logged assessment: {data.get('name', 'anonymous')}", flush=True)
            return sheet_id

    _run_gws([
        "sheets", "spreadsheets", "values", "append",
        "--params", json.dumps({
            "spreadsheetId": sheet_id,
            "range": col_range,
            "valueInputOption": "RAW",
            "insertDataOption": "INSERT_ROWS",
        }),
        "--body", json.dumps({"values": [row]}),
    ])

    return sheet_id
