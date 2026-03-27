"""
Intake Form Generator — creates a professional intake summary from call data
and sends it as a Gmail draft to the assigned attorney.

Usage:
    python -m tools.legal_receptionist.intake_form --transcript .tmp/voice-transcripts/latest.json
    python -m tools.legal_receptionist.intake_form --demo  (generates a sample)
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()


def extract_fields_from_transcript(transcript_data):
    """Extract intake fields from a Retell call transcript using Claude.

    Args:
        transcript_data: dict with 'transcript' (str) and optionally 'summary' (str)

    Returns:
        dict of extracted fields
    """
    import anthropic

    transcript = transcript_data.get("transcript", "")
    summary = transcript_data.get("summary", "")

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"""Extract intake information from this law firm receptionist call transcript.
Return a JSON object with these fields (use empty string if not found):

- caller_name
- phone
- email
- practice_area (one of: Divorce / Separation, Child Custody, Child Support, Protective / Restraining Orders, Mediation)
- matter_summary (2-3 sentence summary of their situation)
- urgency (emergency, high, standard, low)
- opposing_party
- children (yes/no/unknown + details)
- consultation_date
- consultation_time
- consultation_format (In-Office, Video, Phone)
- attorney_name
- how_found
- special_notes (anything notable the attorney should know)

TRANSCRIPT:
{transcript}

{f"CALL SUMMARY: {summary}" if summary else ""}

Return ONLY the JSON object, no other text."""
        }],
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return {"error": "Failed to extract fields", "raw": response.content[0].text}


def build_intake_html(fields, call_metadata=None):
    """Build a professional HTML intake form from extracted fields."""
    meta = call_metadata or {}
    ts = meta.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M"))
    call_id = meta.get("call_id", "N/A")
    duration = meta.get("duration_ms", 0)
    duration_str = f"{duration / 1000:.0f}s" if duration else "N/A"

    name = fields.get("caller_name", "Unknown")
    phone = fields.get("phone", "")
    email = fields.get("email", "")
    area = fields.get("practice_area", "")
    summary = fields.get("matter_summary", "")
    urgency = fields.get("urgency", "standard")
    opposing = fields.get("opposing_party", "")
    children = fields.get("children", "")
    consult_date = fields.get("consultation_date", "")
    consult_time = fields.get("consultation_time", "")
    consult_format = fields.get("consultation_format", "")
    attorney = fields.get("attorney_name", "")
    how_found = fields.get("how_found", "")
    notes = fields.get("special_notes", "")

    urgency_color = {
        "emergency": "#FF4D4D",
        "high": "#FFB020",
        "standard": "#00D4AA",
        "low": "#888888",
    }.get(urgency.lower(), "#888888")

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:'Segoe UI',Arial,sans-serif;">
<div style="max-width:640px;margin:20px auto;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">

    <!-- Header -->
    <div style="background:#1C1C20;padding:24px 32px;color:#ffffff;">
        <h1 style="margin:0;font-size:20px;font-weight:600;">New Client Intake</h1>
        <p style="margin:6px 0 0;font-size:13px;color:#00D4AA;">Brennan &amp; Clark Family Law &mdash; AI Receptionist</p>
    </div>

    <!-- Urgency Banner -->
    <div style="background:{urgency_color};padding:8px 32px;color:#ffffff;font-size:13px;font-weight:600;text-transform:uppercase;">
        Urgency: {urgency}
    </div>

    <!-- Client Info -->
    <div style="padding:24px 32px;">
        <h2 style="font-size:16px;color:#1C1C20;margin:0 0 16px;border-bottom:2px solid #00D4AA;padding-bottom:8px;">Client Information</h2>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="padding:6px 0;color:#666;width:140px;">Name</td><td style="padding:6px 0;font-weight:600;">{name}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Phone</td><td style="padding:6px 0;">{phone}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Email</td><td style="padding:6px 0;">{email}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Referral Source</td><td style="padding:6px 0;">{how_found or 'Phone inquiry'}</td></tr>
        </table>
    </div>

    <!-- Matter Details -->
    <div style="padding:0 32px 24px;">
        <h2 style="font-size:16px;color:#1C1C20;margin:0 0 16px;border-bottom:2px solid #00D4AA;padding-bottom:8px;">Matter Details</h2>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="padding:6px 0;color:#666;width:140px;">Practice Area</td><td style="padding:6px 0;font-weight:600;">{area}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Opposing Party</td><td style="padding:6px 0;">{opposing or 'Not provided'}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Children</td><td style="padding:6px 0;">{children or 'Not discussed'}</td></tr>
        </table>
        <div style="margin-top:12px;padding:12px;background:#f8f8f8;border-left:3px solid #00D4AA;border-radius:4px;">
            <p style="margin:0;font-size:13px;color:#666;">Matter Summary</p>
            <p style="margin:6px 0 0;font-size:14px;color:#1C1C20;">{summary or 'Details to be discussed during consultation.'}</p>
        </div>
        {f'<div style="margin-top:12px;padding:12px;background:#fff8e6;border-left:3px solid #FFB020;border-radius:4px;"><p style="margin:0;font-size:13px;color:#666;">Special Notes</p><p style="margin:6px 0 0;font-size:14px;color:#1C1C20;">{notes}</p></div>' if notes else ''}
    </div>

    <!-- Consultation -->
    <div style="padding:0 32px 24px;">
        <h2 style="font-size:16px;color:#1C1C20;margin:0 0 16px;border-bottom:2px solid #00D4AA;padding-bottom:8px;">Scheduled Consultation</h2>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="padding:6px 0;color:#666;width:140px;">Date</td><td style="padding:6px 0;font-weight:600;">{consult_date or 'Pending'}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Time</td><td style="padding:6px 0;">{consult_time or 'Pending'}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Format</td><td style="padding:6px 0;">{consult_format or 'TBD'}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Attorney</td><td style="padding:6px 0;">{attorney or 'To be assigned'}</td></tr>
        </table>
    </div>

    <!-- Footer -->
    <div style="background:#f8f8f8;padding:16px 32px;border-top:1px solid #eee;">
        <p style="margin:0;font-size:11px;color:#999;">
            Call ID: {call_id} &bull; Duration: {duration_str} &bull; Captured: {ts}<br>
            Generated by AI Receptionist &mdash; Powered by Ledger.AI
        </p>
    </div>

</div>
</body>
</html>"""
    return html


def send_intake_email(fields, call_metadata=None, recipient=None):
    """Send the intake form as an HTML email directly.

    Args:
        fields: extracted intake fields dict
        call_metadata: optional call info (call_id, duration, timestamp)
        recipient: email to send to (defaults to jon@getledger.net for demo)
    """
    import base64
    import shutil
    import subprocess
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    NPX_PATH = shutil.which("npx") or r"C:\Program Files\nodejs\npx.cmd"

    name = fields.get("caller_name", "New Client")
    area = fields.get("practice_area", "Family Law")
    urgency = fields.get("urgency", "standard").upper()
    to = recipient or os.environ.get("INTAKE_EMAIL", "jon@getledger.net")

    subject = f"[INTAKE] {name} - {area} ({urgency})"
    html_body = build_intake_html(fields, call_metadata)

    msg = MIMEMultipart("alternative")
    msg["to"] = to
    msg["from"] = "jon@getledger.net"
    msg["subject"] = subject

    # Plain text fallback
    plain = (
        f"New Client Intake: {name}\n"
        f"Practice Area: {area}\n"
        f"Phone: {fields.get('phone', '')}\n"
        f"Email: {fields.get('email', '')}\n"
        f"Urgency: {urgency}\n"
        f"Summary: {fields.get('matter_summary', '')}\n"
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    try:
        cmd = [NPX_PATH, "@googleworkspace/cli",
               "gmail", "users", "messages", "send",
               "--params", json.dumps({"userId": "me"}),
               "--json", json.dumps({"raw": raw})]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=(os.name == "nt"))
        if result.returncode != 0:
            raise RuntimeError(f"Gmail send error: {result.stderr.strip()}")

        output = result.stdout.strip()
        for i, ch in enumerate(output):
            if ch in "{[":
                try:
                    data = json.loads(output[i:])
                    return {"status": "sent", "message_id": data.get("id", "")}
                except json.JSONDecodeError:
                    continue
        return {"status": "sent", "message_id": "unknown"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def process_transcript_file(filepath, recipient=None):
    """Process a saved transcript file into an intake form and Gmail draft.

    Args:
        filepath: path to transcript JSON file
        recipient: optional email override
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Processing transcript: {filepath}")
    print(f"  Call ID: {data.get('call_id', 'N/A')}")
    print(f"  Duration: {data.get('duration_ms', 0) / 1000:.0f}s")

    # Extract fields from transcript
    print("  Extracting intake fields...")
    fields = extract_fields_from_transcript(data)

    if fields.get("error"):
        print(f"  Error: {fields['error']}")
        return None

    print(f"  Caller: {fields.get('caller_name', '?')}")
    print(f"  Practice Area: {fields.get('practice_area', '?')}")

    # Save extracted fields
    fields_path = filepath.replace(".json", "_fields.json")
    with open(fields_path, "w", encoding="utf-8") as f:
        json.dump(fields, f, indent=2)
    print(f"  Fields saved: {fields_path}")

    # Save HTML form
    html = build_intake_html(fields, {
        "call_id": data.get("call_id", ""),
        "duration_ms": data.get("duration_ms", 0),
        "timestamp": data.get("timestamp", ""),
    })
    html_path = filepath.replace(".json", "_intake.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Intake form saved: {html_path}")

    # Create Gmail draft
    to = recipient or os.environ.get("INTAKE_EMAIL", "jon@getledger.net")
    print(f"  Sending intake form to {to}...")
    try:
        result = send_intake_email(fields, {
            "call_id": data.get("call_id", ""),
            "duration_ms": data.get("duration_ms", 0),
            "timestamp": data.get("timestamp", ""),
        }, recipient=to)
        print(f"  Email sent: {result.get('message_id', 'unknown')}")
    except Exception as e:
        print(f"  Draft failed: {e}")

    return fields


def main():
    parser = argparse.ArgumentParser(description="Generate intake form from call transcript")
    parser.add_argument("--transcript", help="Path to transcript JSON file")
    parser.add_argument("--to", default=None, help="Recipient email (default: jon@getledger.net)")
    parser.add_argument("--demo", action="store_true", help="Generate a demo intake form")
    args = parser.parse_args()

    if args.demo:
        demo_fields = {
            "caller_name": "Dana Daughtry",
            "phone": "(856) 555-0199",
            "email": "dana.daughtry@gmail.com",
            "practice_area": "Divorce / Separation",
            "matter_summary": "Caller is seeking divorce from spouse of 8 years. Reports disagreements on property division and custody of two children (ages 5 and 8). Currently living separately. No paperwork filed yet.",
            "urgency": "standard",
            "opposing_party": "Mark Daughtry",
            "children": "Yes, two children ages 5 and 8",
            "consultation_date": "2026-03-27",
            "consultation_time": "10:00 AM",
            "consultation_format": "Phone",
            "attorney_name": "Sarah Brennan",
            "how_found": "Google Search",
            "special_notes": "Caller mentioned concerns about spouse hiding financial assets. Attorney should discuss asset discovery process.",
        }
        html = build_intake_html(demo_fields, {
            "call_id": "demo_001",
            "duration_ms": 245000,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

        os.makedirs(".tmp/voice-transcripts", exist_ok=True)
        path = ".tmp/voice-transcripts/demo_intake.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Demo intake form saved: {path}")

        if args.to:
            print(f"Creating draft to {args.to}...")
            result = send_intake_email(demo_fields, recipient=args.to)
            print(f"Draft created: {result}")

        # Open in browser
        import subprocess
        subprocess.Popen(["cmd", "/c", "start", "", os.path.abspath(path)], shell=True)
        return

    if args.transcript:
        process_transcript_file(args.transcript, recipient=args.to)
    else:
        # Process most recent transcript
        transcript_dir = ".tmp/voice-transcripts"
        if not os.path.isdir(transcript_dir):
            print("No transcripts found. Make a call first.")
            return

        files = sorted(
            [f for f in os.listdir(transcript_dir) if f.endswith(".json") and not f.endswith("_fields.json")],
            reverse=True,
        )
        if not files:
            print("No transcripts found.")
            return

        process_transcript_file(os.path.join(transcript_dir, files[0]), recipient=args.to)


if __name__ == "__main__":
    main()
