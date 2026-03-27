"""
Google Calendar scheduling for legal receptionist consultations.

Uses Google Calendar Python API (service account) on Render,
falls back to npx Google Workspace CLI locally.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta

NPX_PATH = shutil.which("npx") or r"C:\Program Files\nodejs\npx.cmd"
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

_GWS_AVAILABLE = shutil.which("npx") is not None


def _use_python_api():
    """Check if we should use the Python Google API client."""
    try:
        from app.google_api import is_available
        return is_available()
    except ImportError:
        return False


def _run_calendar_npx(args_list):
    """Run a Google Workspace CLI calendar command and return parsed JSON."""
    cmd = [NPX_PATH, "@googleworkspace/cli"] + args_list
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, shell=(os.name == "nt")
    )
    if result.returncode != 0:
        raise RuntimeError(f"Calendar CLI error: {result.stderr.strip()}")
    output = result.stdout.strip()
    for i, ch in enumerate(output):
        if ch in "{[":
            try:
                return json.loads(output[i:])
            except json.JSONDecodeError:
                continue
    return None


def _tz_offset():
    """Get local timezone offset string (e.g., '-04:00')."""
    now = datetime.now()
    utc_now = datetime.utcnow()
    delta = now - utc_now
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(abs(total_seconds), 3600)
    minutes = remainder // 60
    sign = "+" if total_seconds >= 0 else "-"
    return f"{sign}{hours:02d}:{minutes:02d}"


def _list_events_api(time_min, time_max):
    """List events using Python Google API client."""
    from app.google_api import get_calendar_service
    service = get_calendar_service()
    if not service:
        return []
    result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def _insert_event_api(event_body):
    """Insert a calendar event using Python Google API client."""
    from app.google_api import get_calendar_service
    service = get_calendar_service()
    if not service:
        return None
    return service.events().insert(
        calendarId=CALENDAR_ID,
        body=event_body,
    ).execute()


def get_available_slots(days_ahead=5, duration_minutes=30):
    """Get available consultation slots for the next N business days.

    Returns list of {"date": "YYYY-MM-DD", "day": "Monday", "slots": ["10:00 AM", ...]}
    """
    tz = _tz_offset()
    now = datetime.now()
    available = []
    use_api = _use_python_api()

    for day_offset in range(1, days_ahead + 7):
        day = now + timedelta(days=day_offset)

        if day.weekday() >= 5:
            continue

        close_hour = 16 if day.weekday() == 4 else 17

        time_min = day.replace(hour=9, minute=0, second=0).strftime(f"%Y-%m-%dT%H:%M:%S{tz}")
        time_max = day.replace(hour=close_hour, minute=0, second=0).strftime(f"%Y-%m-%dT%H:%M:%S{tz}")

        # Get busy times from calendar
        busy = []
        items = []
        try:
            if use_api:
                items = _list_events_api(time_min, time_max)
            elif _GWS_AVAILABLE:
                result = _run_calendar_npx([
                    "calendar", "events", "list",
                    "--params", json.dumps({
                        "calendarId": CALENDAR_ID,
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "singleEvents": True,
                        "orderBy": "startTime",
                    }),
                ])
                items = result.get("items", []) if result else []
        except Exception as e:
            print(f"[Scheduler] Calendar read error: {e}", flush=True)

        for item in items:
            start = item.get("start", {}).get("dateTime", "")
            end = item.get("end", {}).get("dateTime", "")
            if start and end:
                busy.append((
                    datetime.fromisoformat(start.replace("Z", "+00:00")),
                    datetime.fromisoformat(end.replace("Z", "+00:00")),
                ))

        # Generate 30-min slots from 9am to close, skipping busy
        slots = []
        slot_time = day.replace(hour=9, minute=0, second=0)
        end_time = day.replace(hour=close_hour, minute=0, second=0)

        while slot_time + timedelta(minutes=duration_minutes) <= end_time:
            slot_end = slot_time + timedelta(minutes=duration_minutes)
            is_free = True
            for busy_start, busy_end in busy:
                bs = busy_start.replace(tzinfo=None)
                be = busy_end.replace(tzinfo=None)
                if slot_time < be and slot_end > bs:
                    is_free = False
                    break
            if is_free:
                slots.append(slot_time.strftime("%I:%M %p").lstrip("0"))
            slot_time += timedelta(minutes=30)

        if slots:
            available.append({
                "date": day.strftime("%Y-%m-%d"),
                "day": day.strftime("%A"),
                "slots": slots,
            })

        if len(available) >= days_ahead:
            break

    return available


def book_consultation(date_str, time_str, caller_name, practice_area,
                      attorney_name, matter_summary="", phone="", email="",
                      format_type="In-Office", duration_minutes=30):
    """Book a consultation on Google Calendar."""
    tz = _tz_offset()

    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
    end_dt = dt + timedelta(minutes=duration_minutes)

    start_iso = dt.strftime(f"%Y-%m-%dT%H:%M:%S{tz}")
    end_iso = end_dt.strftime(f"%Y-%m-%dT%H:%M:%S{tz}")

    description = (
        f"INTAKE CONSULTATION\n"
        f"{'=' * 30}\n"
        f"Client: {caller_name}\n"
        f"Phone: {phone}\n"
        f"Email: {email}\n"
        f"Practice Area: {practice_area}\n"
        f"Format: {format_type}\n"
        f"{'=' * 30}\n"
        f"Matter Summary:\n{matter_summary}\n"
        f"{'=' * 30}\n"
        f"Booked by: AI Receptionist"
    )

    event = {
        "summary": f"[INTAKE] {caller_name} - {practice_area}",
        "description": description,
        "start": {"dateTime": start_iso, "timeZone": "America/New_York"},
        "end": {"dateTime": end_iso, "timeZone": "America/New_York"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 60},
                {"method": "popup", "minutes": 15},
            ],
        },
    }

    result = None
    use_api = _use_python_api()

    try:
        if use_api:
            result = _insert_event_api(event)
            print(f"[Scheduler] Booked via API: {caller_name}", flush=True)
        elif _GWS_AVAILABLE:
            result = _run_calendar_npx([
                "calendar", "events", "insert",
                "--params", json.dumps({"calendarId": CALENDAR_ID}),
                "--body", json.dumps(event),
            ])
            print(f"[Scheduler] Booked via npx: {caller_name}", flush=True)
        else:
            print(f"[Scheduler] No calendar backend available for {caller_name}", flush=True)
    except Exception as e:
        print(f"[Scheduler] Booking error: {e}", flush=True)

    return {
        "event_id": result.get("id", "") if result else "pending",
        "date": date_str,
        "time": time_str,
        "attorney": attorney_name,
        "format": format_type,
        "link": result.get("htmlLink", "") if result else "",
    }
