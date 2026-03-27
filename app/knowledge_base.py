"""
Loads firm_data.json and builds the static system prompt context.

This handles firm-specific config that doesn't need vector search:
attorney names, hours, fees, consultation process, conflict list.
RAG (rag.py) handles everything else.
"""

import json
import os

_FIRM_DATA_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "firm_data.json",
)


def load_firm_data(path=None):
    """Load and return the firm data dict."""
    p = path or os.path.normpath(_FIRM_DATA_PATH)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def get_conflict_names(firm_data=None):
    """Return set of lowercase names from the conflict list."""
    data = firm_data or load_firm_data()
    return {entry["name"].lower() for entry in data.get("conflict_list", [])}


def check_conflict(name, firm_data=None):
    """Check if a name matches the conflict list. Returns (bool, match_detail)."""
    conflicts = get_conflict_names(firm_data)
    name_lower = name.strip().lower()
    for entry in (firm_data or load_firm_data()).get("conflict_list", []):
        if entry["name"].lower() == name_lower:
            return True, entry.get("matter", "")
    return False, ""


def get_attorney_for_area(practice_area, firm_data=None):
    """Return the attorney dict assigned to a practice area."""
    data = firm_data or load_firm_data()
    for area in data.get("practice_areas", []):
        if area["name"].lower() == practice_area.lower():
            attorney_name = area.get("attorney", "")
            for atty in data.get("attorneys", []):
                if atty["name"] == attorney_name:
                    return atty
    return data["attorneys"][0] if data.get("attorneys") else None


def build_system_context(firm_data=None):
    """Build the static firm context string for the system prompt."""
    data = firm_data or load_firm_data()

    attorneys_text = ""
    for atty in data.get("attorneys", []):
        specs = ", ".join(atty.get("specialties", []))
        attorneys_text += f"- {atty['name']} ({atty['title']}): {specs}. {atty.get('bio', '')}\n"

    areas_text = ""
    for area in data.get("practice_areas", []):
        fee = area.get("consultation_fee", 0)
        fee_str = f"${fee}" if fee > 0 else "Free"
        note = f" ({area['note']})" if area.get("note") else ""
        areas_text += (
            f"- {area['name']}: {area['description']}. "
            f"Consultation: {fee_str}. Retainer range: ${area.get('typical_retainer', 'varies')}.{note}\n"
        )

    consult = data.get("consultation", {})

    return f"""FIRM: {data['firm_name']}
ADDRESS: {data['address']['street']}, {data['address']['city']}, {data['address']['state']} {data['address']['zip']}
PHONE: {data['phone']}
EMAIL: {data['email']}

ATTORNEYS:
{attorneys_text}
PRACTICE AREAS:
{areas_text}
CONSULTATION DETAILS:
- Duration: {consult.get('duration_minutes', 30)} minutes
- Default fee: ${consult.get('default_fee', 250)}
- Free consultations for: {', '.join(consult.get('free_for', []))}
- Payment methods: {', '.join(consult.get('payment_methods', []))}
- Options: {', '.join(consult.get('location_options', []))}
- {consult.get('booking_notice', '')}
- Cancellation: {consult.get('cancellation_policy', '')}

HOURS:
{chr(10).join(f"- {day.title()}: {hrs}" for day, hrs in data.get('hours', {}).items())}

HOW CALLERS FIND US:
{', '.join(data.get('referral_sources', []))}"""
