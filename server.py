"""
Ledger.AI Onboarding Assistant — Flask Server

Serves the quiz UI, voice agent, scoring, insight generation, and Sheets logging.

Local:  python server.py
Deploy: gunicorn server:app
"""

import os
import sys
import json
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from flask import Flask, request, jsonify, send_file

from app.scorer import calculate_score, generate_insight
from app.sheets import log_assessment
from app.email_sender import send_confirmation
from app.config import CALENDAR_BOOKING_URL

app = Flask(__name__, static_folder="static", static_url_path="/static")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_file("static/index.html")


# ---------------------------------------------------------------------------
# Quiz API
# ---------------------------------------------------------------------------

@app.route("/assess", methods=["POST"])
def assess():
    """Score quiz answers and generate personalized insight."""
    data = request.get_json()
    answers = data.get("answers", {})

    if not answers:
        return jsonify({"error": "No answers provided"}), 400

    result = calculate_score(answers)
    insight = generate_insight(answers, result["score"], result["level"])

    return jsonify({
        "score": result["score"],
        "level": result["level"],
        "level_color": result["level_color"],
        "breakdown": result["breakdown"],
        "insight": insight,
        "booking_url": CALENDAR_BOOKING_URL,
    })


@app.route("/log", methods=["POST"])
def log():
    """Log assessment + contact info to Google Sheets and send confirmation email."""
    data = request.get_json()

    try:
        log_assessment(data)
    except Exception as e:
        print(f"[Log] Sheets error: {e}", flush=True)

    # Send confirmation email
    email = data.get("email", "")
    name = data.get("name", "")
    if email and name:
        data["source"] = data.get("source", "text")
        send_confirmation(email, name, data)

    return jsonify({"status": "logged"})


# ---------------------------------------------------------------------------
# Voice Agent (Retell AI)
# ---------------------------------------------------------------------------

@app.route("/web-call", methods=["POST"])
def web_call():
    """Create a Retell web call session for the voice assessment."""
    try:
        from retell import Retell

        retell = Retell(api_key=os.environ.get("RETELL_API_KEY", ""))
        agent_id = os.environ.get("RETELL_AGENT_ID", "")

        if not agent_id:
            return jsonify({"error": "Voice agent not configured"}), 500

        call = retell.call.create_web_call(agent_id=agent_id)
        print(f"[Voice] Web call created: {call.call_id}", flush=True)

        return jsonify({
            "access_token": call.access_token,
            "call_id": call.call_id,
        })
    except Exception as e:
        print(f"[Voice] Web call error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@app.route("/post-call", methods=["POST"])
def post_call():
    """
    Webhook from Retell after call_analyzed event.
    Extracts assessment data from transcript and logs to Sheets.
    """
    data = request.get_json()
    event = data.get("event", "")

    if event != "call_analyzed":
        return jsonify({"status": "ignored", "event": event})

    call_data = data.get("data", {})
    call_id = call_data.get("call_id", "unknown")
    transcript = call_data.get("transcript", "")
    duration_ms = call_data.get("duration_ms", 0)
    call_analysis = call_data.get("call_analysis", {})

    print(f"[Voice] Post-call webhook: {call_id} ({duration_ms}ms)", flush=True)

    # Skip very short calls (< 15 seconds)
    if duration_ms < 15000:
        print(f"[Voice] Call too short, skipping: {duration_ms}ms", flush=True)
        return jsonify({"status": "skipped", "reason": "too_short"})

    # Extract assessment data from transcript using Claude
    extracted = _extract_from_transcript(transcript, call_analysis)

    if extracted:
        extracted["source"] = "voice"
        try:
            log_assessment(extracted)
            print(f"[Voice] Logged voice assessment: {extracted.get('name', 'anonymous')}", flush=True)
        except Exception as e:
            print(f"[Voice] Sheets log error: {e}", flush=True)

        # Send confirmation email if we have their email
        email = extracted.get("email", "")
        name = extracted.get("name", "")
        if email and name:
            send_confirmation(email, name, extracted)

    # Save transcript to .tmp for reference
    _save_transcript(call_id, data)

    return jsonify({"status": "processed", "call_id": call_id})


def _extract_from_transcript(transcript, call_analysis):
    """Use Claude to extract assessment fields from a voice conversation transcript."""
    if not transcript or len(transcript) < 50:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic()

        prompt = f"""Extract the following fields from this voice conversation transcript between an AI consultant (Ledger) and a business prospect. Return ONLY valid JSON, nothing else.

Fields to extract (use empty string if not mentioned):
- name: prospect's name
- email: prospect's email
- company: prospect's company name
- industry: their industry
- team_size: team size (e.g., "Just me", "2-10", "11-50", "51-200", "200+")
- ai_tools: list of AI tools they currently use (array of strings, empty array if none)
- pain_point: where they lose the most time (comma-separated if multiple)
- ai_goal: what they want from AI (comma-separated if multiple)
- booked: true if they agreed to book a discovery call, false otherwise

Transcript:
{transcript}

Additional analysis (if available):
{json.dumps(call_analysis) if call_analysis else 'None'}

Return JSON only:"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        # Extract JSON from response
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        extracted = json.loads(text)

        # Add metadata
        extracted["source"] = "voice"
        extracted["score"] = 0
        extracted["level"] = "Voice Assessment"
        extracted["insight"] = "Assessment conducted via voice conversation"

        # Run scoring if we have enough data
        answers = {
            "industry": extracted.get("industry", ""),
            "team_size": extracted.get("team_size", ""),
            "ai_tools": extracted.get("ai_tools", []),
            "pain_point": extracted.get("pain_point", ""),
            "ai_goal": extracted.get("ai_goal", ""),
        }
        if answers["industry"] or answers["team_size"]:
            result = calculate_score(answers)
            extracted["score"] = result["score"]
            extracted["level"] = result["level"]
            insight = generate_insight(answers, result["score"], result["level"])
            extracted["insight"] = insight

        return extracted

    except Exception as e:
        print(f"[Voice] Transcript extraction failed: {e}", flush=True)
        return None


def _save_transcript(call_id, data):
    """Save call transcript to .tmp for reference."""
    try:
        tmp_dir = os.path.join(ROOT, ".tmp", "voice-transcripts")
        os.makedirs(tmp_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(tmp_dir, f"{ts}_{call_id}.json")
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[Voice] Transcript saved: {filepath}", flush=True)
    except Exception as e:
        print(f"[Voice] Transcript save failed: {e}", flush=True)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Local dev
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
