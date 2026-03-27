"""
Legal Receptionist configuration — practice areas, disclaimers, escalation rules,
intake stages, and Google Sheets config.
"""

# ---------------------------------------------------------------------------
# Practice areas supported
# ---------------------------------------------------------------------------
PRACTICE_AREAS = [
    "Divorce / Separation",
    "Child Custody",
    "Child Support",
    "Protective / Restraining Orders",
    "Mediation",
    "Other Family Law",
]

# ---------------------------------------------------------------------------
# Intake stages (conversation flow)
# ---------------------------------------------------------------------------
INTAKE_STAGES = [
    "GREETING",
    "IDENTITY",
    "MATTER_TYPE",
    "FACTS",
    "URGENCY",
    "CONFLICT_CHECK",
    "SCHEDULING",
    "WRAP_UP",
]

# Required fields per stage
STAGE_FIELDS = {
    "IDENTITY": ["caller_name", "phone", "email"],
    "MATTER_TYPE": ["practice_area"],
    "FACTS": ["matter_summary"],
    "URGENCY": ["urgency_level"],
    "CONFLICT_CHECK": ["opposing_party"],
    "SCHEDULING": ["preferred_time"],
}

# ---------------------------------------------------------------------------
# Urgency levels
# ---------------------------------------------------------------------------
URGENCY_LEVELS = {
    "EMERGENCY": "Immediate safety concern, active restraining order violation, child in danger",
    "HIGH": "Court deadline within 7 days, served with papers, arrest",
    "STANDARD": "Considering divorce, custody modification, general inquiry",
    "LOW": "Information gathering, no active legal matter",
}

# ---------------------------------------------------------------------------
# Escalation triggers — keywords/phrases that bypass normal flow
# ---------------------------------------------------------------------------
ESCALATION_KEYWORDS = [
    # Crisis / safety
    "hurt me", "hitting me", "abuse", "abused", "domestic violence",
    "restraining order", "protection order", "scared for my life",
    "threatened", "emergency", "danger", "unsafe",
    # Distress
    "going to hurt myself", "suicide", "kill myself",
    # Explicit attorney request
    "speak to a lawyer", "speak to an attorney", "talk to a lawyer",
    "talk to the attorney", "get me a real person", "human please",
    # Arrest / criminal overlap
    "just arrested", "in jail", "being detained",
]

# National crisis resources (for safety escalations)
CRISIS_RESOURCES = {
    "domestic_violence": "National Domestic Violence Hotline: 1-800-799-7233",
    "suicide_prevention": "988 Suicide & Crisis Lifeline: call or text 988",
    "child_abuse": "Childhelp National Child Abuse Hotline: 1-800-422-4453",
}

# ---------------------------------------------------------------------------
# Legal disclaimers (NJ Bar compliant)
# ---------------------------------------------------------------------------
DISCLAIMER_OPENING = (
    "I'm an AI assistant for {firm_name}. I can help you schedule a consultation "
    "and collect some initial information, but I cannot provide legal advice. "
    "For legal guidance, you'll want to speak directly with one of our attorneys."
)

DISCLAIMER_LEGAL_QUESTION = (
    "That's a great question, but it's something {attorney_name} would need to "
    "address during your consultation. I'm not able to give legal advice or "
    "interpret how the law applies to your situation. Would you like me to "
    "schedule a consultation so you can discuss this with {attorney_name}?"
)

DISCLAIMER_NO_GUARANTEE = (
    "I want to be upfront: I can't predict outcomes or assess the strength of "
    "any legal matter. Every situation is unique, and only an attorney can "
    "evaluate your specific circumstances after a full review."
)

DISCLAIMER_VOICE = (
    "Before we continue, I should let you know this call may be recorded for "
    "quality and training purposes. Is that okay?"
)

# Phrases that indicate caller is asking for legal advice
LEGAL_ADVICE_TRIGGERS = [
    "do i have a case", "do i have a strong case", "will i win",
    "what are my chances", "should i file", "can i get custody",
    "how much will i get", "what's my case worth", "am i entitled",
    "what should i do", "is this legal", "can they do that",
    "what does the law say", "what are my rights", "how does the court",
    "will the judge", "can i sue",
]

# ---------------------------------------------------------------------------
# Google Sheets config — Intake Log
# ---------------------------------------------------------------------------
SHEET_TITLE = "Legal Receptionist Intake Log"

INTAKE_HEADERS = [
    "Timestamp",
    "Session ID",
    "Caller Name",
    "Phone",
    "Email",
    "Practice Area",
    "Matter Summary",
    "Urgency",
    "Opposing Party",
    "Conflict Flag",
    "Outcome",
    "Notes",
    "How Found Us",
]

OUTCOME_TYPES = [
    "Consultation Scheduled",
    "Message Taken",
    "Escalated to Attorney",
    "Crisis Referral",
    "Information Only",
    "Abandoned",
]

# ---------------------------------------------------------------------------
# RAG config
# ---------------------------------------------------------------------------
PINECONE_INDEX_NAME = "legal-receptionist"
PINECONE_NAMESPACE = "family-law"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
RAG_TOP_K = 5
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# ---------------------------------------------------------------------------
# Voice config (Phase 2 — Retell AI)
# ---------------------------------------------------------------------------
RETELL_VOICE_ID = ""  # Set after selecting voice in Retell dashboard
RETELL_AGENT_NAME = "Legal Intake Assistant"

# ---------------------------------------------------------------------------
# Business hours (demo firm)
# ---------------------------------------------------------------------------
BUSINESS_HOURS = {
    "monday": ("09:00", "17:00"),
    "tuesday": ("09:00", "17:00"),
    "wednesday": ("09:00", "17:00"),
    "thursday": ("09:00", "17:00"),
    "friday": ("09:00", "16:00"),
    "saturday": None,
    "sunday": None,
}

TIMEZONE = "America/New_York"
