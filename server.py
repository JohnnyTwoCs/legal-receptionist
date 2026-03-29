"""
Combined Flask server for the Onboarding Assistant.

Serves the chat UI, voice demo, Retell tool endpoints, and post-call webhooks.
Single deployable service for Render.

Local:  python server.py
Deploy: gunicorn server:app
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta

# Ensure project root is on path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from flask import Flask, request, jsonify, send_file

from app.intake import IntakeSession
from app.sheets import log_intake, get_intakes
from app.scheduler import get_available_slots, book_consultation
from app.knowledge_base import load_firm_data, get_attorney_for_area

app = Flask(__name__, static_folder="static", static_url_path="/static")
firm_data = load_firm_data()

# In-memory chat sessions
sessions = {}


def _get_session(session_id=None, channel="chat"):
    if session_id and session_id in sessions:
        return sessions[session_id]
    session = IntakeSession(channel=channel)
    sessions[session.session_id] = session
    return session


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_file("static/demo.html")


@app.route("/chat-demo")
def chat_demo():
    return send_file("static/index.html")


@app.route("/voice-demo")
def voice_demo():
    return send_file("static/voice.html")


# ---------------------------------------------------------------------------
# Chat API
# ---------------------------------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    session_id = data.get("session_id")

    if not message:
        return jsonify({"error": "Empty message"}), 400

    session = _get_session(session_id)
    result = session.process_message(message)

    if result["stage"] in ("WRAP_UP", "ESCALATION", "CONFLICT_FLAGGED"):
        if not session.outcome:
            session.outcome = result.get("outcome", "Information Only")
        try:
            log_intake(session.get_summary())
        except Exception as e:
            print(f"Warning: Failed to log intake: {e}")

    return jsonify({
        "response": result["response"],
        "fields": result["fields"],
        "stage": result["stage"],
        "escalation": result["escalation"],
        "session_id": session.session_id,
    })


@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json() or {}
    session_id = data.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]
    session = _get_session()
    return jsonify({"session_id": session.session_id, "message": "Session reset."})


@app.route("/slots")
def slots():
    try:
        return jsonify({"slots": get_available_slots()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/dashboard")
def dashboard():
    try:
        return jsonify({"intakes": get_intakes(limit=50)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Voice: Retell Web Call
# ---------------------------------------------------------------------------

@app.route("/web-call", methods=["POST"])
def web_call():
    try:
        from retell import Retell
        retell = Retell(api_key=os.environ.get("RETELL_API_KEY", ""))
        agent_id = os.environ.get("RETELL_AGENT_ID", "")
        call = retell.call.create_web_call(agent_id=agent_id)
        return jsonify({"access_token": call.access_token, "call_id": call.call_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Retell Tool Endpoints
# ---------------------------------------------------------------------------

def _parse_date(date_str):
    if not date_str:
        return ""
    clean = date_str.strip().lower()

    if re.match(r"^\d{4}-\d{2}-\d{2}$", clean):
        return clean

    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", clean)
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"

    now = datetime.now()

    if "tomorrow" in clean:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for mname, mnum in month_names.items():
        if mname in clean:
            day_match = re.search(r"(\d{1,2})", clean)
            if day_match:
                day = int(day_match.group(1))
                year = now.year
                year_match = re.search(r"(\d{4})", clean)
                if year_match:
                    year = int(year_match.group(1))
                return f"{year}-{mnum:02d}-{day:02d}"

    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, name in enumerate(day_names):
        if name in clean:
            delta = (i - now.weekday()) % 7
            if delta == 0:
                delta = 7
            return (now + timedelta(days=delta)).strftime("%Y-%m-%d")

    return date_str


def _parse_time(time_str):
    if not time_str:
        return ""
    clean = time_str.strip().lower().replace(".", "")

    if re.match(r"^\d{1,2}:\d{2}\s*(am|pm)$", clean, re.IGNORECASE):
        return time_str.strip()

    m = re.match(r"^(\d{1,2})\s*(am|pm)$", clean)
    if m:
        return f"{int(m.group(1))}:00 {m.group(2).upper()}"

    m = re.match(r"^(\d{1,2}):(\d{2})\s*(am|pm)$", clean)
    if m:
        return f"{m.group(1)}:{m.group(2)} {m.group(3).upper()}"

    m = re.match(r"^(\d{1,2})$", clean)
    if m:
        hr = int(m.group(1))
        return f"{hr}:00 {'AM' if hr >= 8 else 'PM'}"

    return time_str.strip()


def _get_fee(practice_area):
    for area in firm_data.get("practice_areas", []):
        if area["name"].lower() in practice_area.lower() or practice_area.lower() in area["name"].lower():
            if area.get("consultation_fee", 0) == 0:
                return "free"
            return f"${area['consultation_fee']}"
    return "$250"


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/check-availability", methods=["POST"])
def check_availability():
    data = request.get_json() or {}
    print(f"[Tool] check-availability", flush=True)
    try:
        avail = get_available_slots(days_ahead=5)
        if not avail:
            return jsonify({"available_slots": "We're fully booked for the next 5 business days. I can take your info and have someone call you back."})
        slot_text = ""
        for day in avail[:3]:
            times = ", ".join(day["slots"][:4])
            slot_text += f"{day['day']} {day['date']}: {times}\n"
        return jsonify({"available_slots": slot_text.strip()})
    except Exception as e:
        print(f"[Tool] error: {e}", flush=True)
        return jsonify({"available_slots": "I'm having trouble checking the calendar. Let me take your info and have someone call you."})


@app.route("/book-consultation", methods=["POST"])
def book_consultation_endpoint():
    data = request.get_json() or {}
    print(f"[Tool] book-consultation", flush=True)

    caller_name = data.get("caller_name", "")
    practice_area = data.get("practice_area", "Divorce / Separation")
    date_str = _parse_date(data.get("date", ""))
    time_str = _parse_time(data.get("time", ""))
    format_type = data.get("format_type", "Phone")

    if not caller_name:
        return jsonify({"confirmation": "I need your name to book. What's your full name?"})
    if not date_str or not time_str:
        return jsonify({"confirmation": "I need a specific date and time. Which day and time work for you?"})

    attorney = get_attorney_for_area(practice_area, firm_data)
    attorney_name = attorney["name"] if attorney else "Sarah Brennan"
    fee = _get_fee(practice_area)

    try:
        book_consultation(
            date_str=date_str, time_str=time_str,
            caller_name=caller_name, practice_area=practice_area,
            attorney_name=attorney_name,
            matter_summary=data.get("matter_summary", ""),
            phone=data.get("phone", ""), email=data.get("email", ""),
            format_type=format_type,
        )
        try:
            log_intake({
                "session_id": f"voice-{datetime.now().strftime('%H%M%S')}",
                "caller_name": caller_name,
                "phone": data.get("phone", ""),
                "email": data.get("email", ""),
                "practice_area": practice_area,
                "matter_summary": data.get("matter_summary", ""),
                "urgency": data.get("urgency", "standard"),
                "opposing_party": data.get("opposing_party", ""),
                "conflict_flag": False,
                "outcome": "Consultation Scheduled",
                "how_found": "Phone",
            })
        except Exception as e:
            print(f"[Tool] Sheets error: {e}", flush=True)

        return jsonify({"confirmation": f"Booked: {caller_name} with {attorney_name} on {date_str} at {time_str} via {format_type}. Fee: {fee}. 24-hour cancellation notice required."})
    except Exception as e:
        print(f"[Tool] book error: {e}", flush=True)
        return jsonify({"confirmation": "I wasn't able to book that slot. Let me save your info and have someone call you to confirm."})


@app.route("/save-callback", methods=["POST"])
def save_callback():
    data = request.get_json() or {}
    print(f"[Tool] save-callback", flush=True)
    try:
        log_intake({
            "session_id": f"cb-{datetime.now().strftime('%H%M%S')}",
            "caller_name": data.get("caller_name", "Unknown"),
            "phone": data.get("phone", ""),
            "email": data.get("email", ""),
            "practice_area": data.get("call_type", "callback_request"),
            "matter_summary": data.get("reason", ""),
            "urgency": "standard",
            "opposing_party": "",
            "conflict_flag": False,
            "outcome": "Callback Requested",
            "how_found": "Phone",
        })
        return jsonify({"result": f"Callback saved. Someone from the office will reach out within one business day."})
    except Exception as e:
        print(f"[Tool] save-callback error: {e}", flush=True)
        return jsonify({"result": "I've noted the request. Someone will follow up within one business day."})


@app.route("/send-confirmation", methods=["POST"])
def send_confirmation():
    data = request.get_json() or {}
    print(f"[Tool] send-confirmation", flush=True)
    email = data.get("email", "")
    if not email:
        return jsonify({"result": "No email provided. Confirmation will be sent via callback."})

    try:
        from app.intake_form import send_intake_email
        fields = {
            "caller_name": data.get("caller_name", ""),
            "phone": data.get("phone", ""),
            "email": email,
            "practice_area": data.get("practice_area", ""),
            "matter_summary": data.get("matter_summary", ""),
            "urgency": "standard",
            "opposing_party": data.get("opposing_party", ""),
            "children": data.get("children", ""),
            "consultation_date": data.get("date", ""),
            "consultation_time": data.get("time", ""),
            "consultation_format": data.get("format_type", ""),
            "attorney_name": data.get("attorney_name", ""),
            "how_found": "Phone",
            "special_notes": "",
        }
        result = send_intake_email(fields, {
            "call_id": "live",
            "duration_ms": 0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }, recipient=email)
        print(f"[Tool] Confirmation sent to {email}: {result}", flush=True)
        return jsonify({"result": f"Confirmation email sent to {email}."})
    except Exception as e:
        print(f"[Tool] send-confirmation error: {e}", flush=True)
        return jsonify({"result": "Couldn't send email, but your appointment is booked. You'll get a follow-up call."})


# ---------------------------------------------------------------------------
# Post-call webhook
# ---------------------------------------------------------------------------

@app.route("/post-call", methods=["POST"])
def post_call_webhook():
    data = request.get_json() or {}
    event_type = data.get("event", "")
    print(f"[Webhook] {event_type}", flush=True)

    if event_type == "call_analyzed":
        call = data.get("call", {})
        transcript = call.get("transcript", "")
        call_summary = call.get("call_analysis", {}).get("call_summary", "")
        call_id = call.get("call_id", "")
        duration = call.get("duration_ms", 0)

        print(f"[Webhook] Call {call_id}: {len(transcript)} chars, {duration/1000:.0f}s", flush=True)

        # Save transcript
        transcript_dir = os.path.join(ROOT, ".tmp", "voice-transcripts")
        os.makedirs(transcript_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(transcript_dir, f"{ts}_{call_id[:12]}.json"), "w") as f:
            json.dump({"call_id": call_id, "timestamp": ts, "duration_ms": duration,
                        "transcript": transcript, "summary": call_summary}, f, indent=2)

        if len(transcript) < 100 or duration < 30000:
            print(f"[Webhook] Short call, skipping intake email", flush=True)
            return jsonify({"status": "ok"})

        try:
            from app.intake_form import extract_fields_from_transcript, send_intake_email
            fields = extract_fields_from_transcript({"transcript": transcript, "summary": call_summary})
            if not fields.get("error"):
                caller_email = fields.get("email", "")
                if caller_email and "@" in caller_email:
                    result = send_intake_email(fields, {"call_id": call_id, "duration_ms": duration, "timestamp": ts}, recipient=caller_email)
                    print(f"[Webhook] Intake email sent to {caller_email}: {result}", flush=True)
        except Exception as e:
            print(f"[Webhook] Intake email error: {e}", flush=True)

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"\n  Onboarding Assistant running at http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=True)
