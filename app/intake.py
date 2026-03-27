"""
Core conversation engine for the legal receptionist.

Stage-based intake flow using Claude API with RAG context injection.
Handles disclaimers, escalation detection, conflict checks, and natural confirmation.
"""

import os
import re
import uuid
import json
from datetime import datetime

import anthropic

from app.config import (
    INTAKE_STAGES,
    STAGE_FIELDS,
    ESCALATION_KEYWORDS,
    CRISIS_RESOURCES,
    DISCLAIMER_OPENING,
    DISCLAIMER_LEGAL_QUESTION,
    LEGAL_ADVICE_TRIGGERS,
    URGENCY_LEVELS,
)
from app.knowledge_base import (
    load_firm_data,
    build_system_context,
    check_conflict,
    get_attorney_for_area,
)
from app.rag import build_rag_context


CLAUDE_MODEL_CHAT = "claude-sonnet-4-20250514"
CLAUDE_MODEL_VOICE = "claude-haiku-4-5-20251001"  # Faster for real-time voice


class IntakeSession:
    """Manages a single intake conversation."""

    def __init__(self, firm_data=None, channel="chat"):
        self.session_id = str(uuid.uuid4())[:8]
        self.firm_data = firm_data or load_firm_data()
        self.channel = channel  # "chat" or "voice"
        self.stage = "GREETING"
        self.fields = {
            "caller_name": "",
            "phone": "",
            "email": "",
            "practice_area": "",
            "matter_summary": "",
            "urgency_level": "",
            "opposing_party": "",
            "preferred_time": "",
            "how_found": "",
            "conflict_flag": False,
            "conflict_detail": "",
            "escalation_triggered": False,
            "escalation_reason": "",
        }
        self.messages = []
        self.outcome = ""
        self.created_at = datetime.now().isoformat()

    def _build_system_prompt(self, user_message=""):
        """Build the full system prompt with firm context, RAG, and instructions."""
        firm_context = build_system_context(self.firm_data)

        # Get RAG context for the user's message
        rag_context = ""
        if user_message:
            rag_context = build_rag_context(user_message)

        collected = {k: v for k, v in self.fields.items() if v and k not in ("conflict_flag", "conflict_detail", "escalation_triggered", "escalation_reason")}
        collected_str = json.dumps(collected, indent=2) if collected else "None yet"

        firm_name = self.firm_data["firm_name"]
        primary_attorney = self.firm_data["attorneys"][0]["name"] if self.firm_data.get("attorneys") else "our attorney"

        channel_label = "online chat" if self.channel == "chat" else "phone call"
        system = f"""You are the receptionist for {firm_name}, a family law firm in South Jersey.

CHANNEL: This is a {channel_label}. {"The person is TYPING to you in a chat window, NOT calling on the phone. Never say 'thank you for calling', 'in case we get disconnected', or any phone language. Say 'welcome' or 'thanks for reaching out' instead." if self.channel == "chat" else "The person is on a phone call. The greeting has ALREADY been spoken by the system. Do NOT repeat 'thank you for calling' or the firm name. Just respond naturally to what they said."}

VOICE & TONE:
- Professional and warm, like an experienced legal secretary. Not casual, not robotic.
- NEVER introduce yourself as an AI or mention disclaimers. The UI handles that separately.
- Keep every response to 1-2 sentences MAX. {"On a phone call, shorter is always better. Long responses feel robotic." if self.channel == "voice" else ""} Be efficient; your job is to collect their info and get them to an attorney quickly.
- Confirm info naturally: "Got it, John. Best number is 555-1234?" NOT "Confirming: Name: John Smith, Phone: 555-1234."
- You CAN combine two related asks in one message to move faster (e.g., name + what they're calling about). Don't drag the conversation out.
{("- IMPORTANT: When asking for contact info in chat, ALWAYS ask for phone AND email in the same message. Example: 'Can I get your phone number and email address?'" if self.channel == "chat" else """- On phone calls, ask for one piece of contact info at a time.
- CRITICAL FOR VOICE: When the caller spells out an email, speech-to-text often garbles it. Common STT errors:
  - "roth" heard as "ross", "raw", "rath", "wrath"
  - "period" or "dot" means "."
  - "at" means "@"
  - "g mail" or "gee mail" means "gmail"
  - Letters may be heard as words: "s as in sam" = "s", "j as in john" = "j"
  - If the email doesn't look right, spell it back letter by letter and ask them to confirm.
  - Be patient. It may take 2-3 attempts. Never get frustrated or restart the whole conversation.
  - If after 3 attempts you still can't get it, say: 'No worries, we can get that from you via text. Let me continue with a few more questions.'""")}

HARD RULES:
1. NEVER give legal advice, interpret law, predict outcomes, or assess case strength.
2. If asked a legal question, redirect: "That's something {primary_attorney} can go over with you during your consultation."
3. NEVER make conflict of interest determinations. Flag names for attorney review only.
4. If someone is in crisis or danger, provide crisis resources immediately.

FIRM INFORMATION:
{firm_context}

{f"RELEVANT KNOWLEDGE BASE CONTEXT:{chr(10)}{rag_context}" if rag_context else ""}

CURRENT INTAKE STATE:
- Session: {self.session_id}
- Stage: {self.stage}
- Collected fields: {collected_str}

STAGE FLOW: {' > '.join(INTAKE_STAGES)}

YOUR TASK FOR CURRENT STAGE ({self.stage}):
{self._stage_instructions()}

RESPONSE FORMAT:
First, write your conversational response to the caller.
Then, you MUST ALWAYS end with a JSON block extracting ALL information from the user's message AND from the full conversation so far. This is critical for the intake form.

Available fields:
- caller_name: Full name
- phone: Phone number
- email: Email address
- practice_area: One of: Divorce / Separation, Child Custody, Child Support, Protective / Restraining Orders, Mediation, Other Family Law
- matter_summary: 1-2 sentence summary of their situation (build this up as you learn more)
- urgency_level: "emergency", "high", "standard", or "low"
- opposing_party: Name of spouse/other party
- how_found: How they found the firm
- preferred_time: When they want to meet

ALWAYS output the block, even if no new fields. Include ALL fields known so far (not just new ones):
```fields
{{"caller_name": "Dana Daughtry", "phone": "856-555-1234", "practice_area": "Divorce / Separation", "_advance": true}}
```
If you detect an escalation trigger, include: {{"_escalation": true, "_escalation_reason": "reason"}}
Set _advance to true when the current stage's information has been collected.
"""
        return system

    def _stage_instructions(self):
        """Return specific instructions for the current stage."""
        instructions = {
            "GREETING": (
                "Professional but warm greeting. Use the firm name. DO NOT mention AI or disclaimers. "
                + ("This is a CHAT, not a phone call. Say 'welcome' or 'thanks for reaching out', NEVER 'thank you for calling'. "
                   if self.channel == "chat" else
                   "This is a phone call. 'Thank you for calling' is appropriate. ")
                + "Ask what brings them in and their name in the same message. Two sentences max."
            ),
            "IDENTITY": (
                "You need their phone number and email before moving on. "
                + ("Since this is a CHAT: ask for phone AND email in ONE message. You MUST ask for both. Do NOT skip email. Do NOT ask about their case yet. Stay on contact info until you have both. "
                   if self.channel == "chat" else
                   "Since this is a PHONE CALL: ask for phone first, then email in a separate follow-up. ")
                + "Confirm what you have naturally before advancing."
            ),
            "MATTER_TYPE": (
                "Ask what type of legal matter they're calling about. "
                "If unclear, offer the practice areas: divorce/separation, custody, child support, "
                "protective orders, or mediation. Route to the right attorney based on their answer."
            ),
            "FACTS": (
                "Ask ONE simple question to help the attorney prepare. Plain language only. "
                "Do NOT use legal jargon. Do NOT ask multiple questions or clarify answers they already gave. "
                "If they answer, accept it and move on. Don't dig deeper. The attorney handles the details. "
                + ("On a phone call, keep this to ONE question max, then advance to the next stage. Speed matters." if self.channel == "voice" else "")
            ),
            "URGENCY": (
                "Ask ONE question: 'Is there anything time-sensitive, like a court date coming up?' "
                "If they say no or it sounds standard, move on immediately."
            ),
            "CONFLICT_CHECK": (
                "Ask for the name of the other party involved (spouse, ex, etc.). "
                "This is for a routine conflict check. If they're uncomfortable sharing, that's okay; "
                "note it and move on."
            ),
            "SCHEDULING": (
                "Offer to schedule a consultation. Mention the fee (or that it's free for protective orders). "
                "Offer in-office, video, or phone options. Suggest available times within 2-3 business days."
            ),
            "WRAP_UP": (
                "Confirm all collected information naturally. Provide: date/time, format, attorney name, "
                "fee, what to bring (ID, court documents, financial docs if applicable), and cancellation policy. "
                "Thank them and let them know someone will confirm via email/text."
            ),
        }
        return instructions.get(self.stage, "Continue the conversation naturally.")

    def _detect_escalation(self, message):
        """Check if the message contains escalation triggers."""
        msg_lower = message.lower()
        for keyword in ESCALATION_KEYWORDS:
            if keyword in msg_lower:
                return True, keyword
        return False, ""

    def _detect_legal_question(self, message):
        """Check if the caller is asking for legal advice."""
        msg_lower = message.lower()
        for trigger in LEGAL_ADVICE_TRIGGERS:
            if trigger in msg_lower:
                return True
        return False

    def _parse_fields(self, response_text):
        """Extract the fields JSON block from the model response."""
        match = re.search(r"```fields\s*\n(.*?)\n```", response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return {}
        return {}

    def _clean_response(self, response_text):
        """Remove the fields JSON block from the visible response."""
        return re.sub(r"\s*```fields\s*\n.*?\n```", "", response_text, flags=re.DOTALL).strip()

    def process_message(self, user_message):
        """Process a user message and return the assistant's response.

        Returns dict: {
            "response": str,
            "fields": dict (current state of all fields),
            "stage": str,
            "escalation": bool,
            "outcome": str,
        }
        """
        # Check for escalation
        is_escalation, trigger = self._detect_escalation(user_message)
        if is_escalation:
            self.fields["escalation_triggered"] = True
            self.fields["escalation_reason"] = trigger
            return self._handle_escalation(trigger)

        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        # Build system prompt with RAG context
        system_prompt = self._build_system_prompt(user_message)

        # Call Claude
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        response = client.messages.create(
            model=CLAUDE_MODEL_VOICE if self.channel == "voice" else CLAUDE_MODEL_CHAT,
            max_tokens=1024,
            system=system_prompt,
            messages=self.messages,
        )

        assistant_text = response.content[0].text

        # Parse extracted fields
        extracted = self._parse_fields(assistant_text)
        clean_response = self._clean_response(assistant_text)

        # Update fields
        advance = extracted.pop("_advance", False)
        escalation = extracted.pop("_escalation", False)
        escalation_reason = extracted.pop("_escalation_reason", "")

        for key, value in extracted.items():
            if key in self.fields and value:
                self.fields[key] = value

        # Handle conflict check
        if self.stage == "CONFLICT_CHECK" and self.fields.get("opposing_party"):
            is_conflict, detail = check_conflict(
                self.fields["opposing_party"], self.firm_data
            )
            if is_conflict:
                self.fields["conflict_flag"] = True
                self.fields["conflict_detail"] = detail
                self.messages.append({"role": "assistant", "content": clean_response})
                return self._handle_conflict()

        # Handle model-detected escalation
        if escalation:
            self.fields["escalation_triggered"] = True
            self.fields["escalation_reason"] = escalation_reason
            return self._handle_escalation(escalation_reason)

        # Advance stage if flagged
        if advance:
            self._advance_stage()

        # Add assistant response to history
        self.messages.append({"role": "assistant", "content": clean_response})

        return {
            "response": clean_response,
            "fields": dict(self.fields),
            "stage": self.stage,
            "escalation": False,
            "outcome": self.outcome,
        }

    def _advance_stage(self):
        """Move to the next intake stage."""
        current_idx = INTAKE_STAGES.index(self.stage) if self.stage in INTAKE_STAGES else 0
        if current_idx < len(INTAKE_STAGES) - 1:
            self.stage = INTAKE_STAGES[current_idx + 1]

    def _handle_escalation(self, reason):
        """Handle an escalation event."""
        self.outcome = "Escalated to Attorney"

        crisis_info = ""
        reason_lower = reason.lower()
        if any(w in reason_lower for w in ["hurt", "abuse", "violence", "scared", "danger", "unsafe"]):
            crisis_info = (
                f"\n\nIf you are in immediate danger, please call 911. "
                f"You can also reach the {CRISIS_RESOURCES['domestic_violence']}."
            )
        elif any(w in reason_lower for w in ["suicide", "kill myself", "hurt myself"]):
            crisis_info = (
                f"\n\nIf you're having thoughts of self-harm, please reach out to the "
                f"{CRISIS_RESOURCES['suicide_prevention']}. You don't have to go through this alone."
            )

        response = (
            f"I understand. Let me connect you with someone who can help right away. "
            f"I'm going to make sure one of our attorneys gets your information immediately "
            f"and reaches out to you as soon as possible.{crisis_info}"
        )

        self.messages.append({"role": "assistant", "content": response})

        return {
            "response": response,
            "fields": dict(self.fields),
            "stage": "ESCALATION",
            "escalation": True,
            "outcome": self.outcome,
        }

    def _handle_conflict(self):
        """Handle a conflict flag."""
        self.outcome = "Escalated to Attorney"

        response = (
            "I appreciate you sharing that. I need to flag something for the attorneys "
            "before we proceed with scheduling. This is a routine step our office takes "
            "with every new matter. Someone from our team will call you back within one "
            "business day to follow up. Is the number you gave me the best way to reach you?"
        )

        self.messages.append({"role": "assistant", "content": response})

        return {
            "response": response,
            "fields": dict(self.fields),
            "stage": "CONFLICT_FLAGGED",
            "escalation": False,
            "outcome": self.outcome,
        }

    def get_summary(self):
        """Return a structured summary of the intake for logging."""
        return {
            "session_id": self.session_id,
            "timestamp": self.created_at,
            "caller_name": self.fields.get("caller_name", ""),
            "phone": self.fields.get("phone", ""),
            "email": self.fields.get("email", ""),
            "practice_area": self.fields.get("practice_area", ""),
            "matter_summary": self.fields.get("matter_summary", ""),
            "urgency": self.fields.get("urgency_level", ""),
            "opposing_party": self.fields.get("opposing_party", ""),
            "conflict_flag": self.fields.get("conflict_flag", False),
            "outcome": self.outcome,
            "how_found": self.fields.get("how_found", ""),
        }
