"""
Ledger.AI Onboarding Assistant — Flask Server

Serves the quiz UI and handles scoring, insight generation, and Sheets logging.

Local:  python server.py
Deploy: gunicorn server:app
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from flask import Flask, request, jsonify, send_file

from app.scorer import calculate_score, generate_insight
from app.sheets import log_assessment
from app.config import CALENDAR_BOOKING_URL

app = Flask(__name__, static_folder="static", static_url_path="/static")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_file("static/index.html")


# ---------------------------------------------------------------------------
# API
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
    """Log assessment + contact info to Google Sheets."""
    data = request.get_json()

    try:
        log_assessment(data)
        return jsonify({"status": "logged"})
    except Exception as e:
        print(f"[Log] Sheets error: {e}", flush=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Local dev
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
