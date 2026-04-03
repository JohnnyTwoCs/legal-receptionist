"""
Configuration for the Ledger.AI Onboarding Assistant.
Scoring weights, readiness levels, and sheet config.
"""

# ---------------------------------------------------------------------------
# Quiz Options & Scoring Weights
# ---------------------------------------------------------------------------

INDUSTRY_SCORES = {
    "Professional Services": 10,
    "Financial Services": 10,
    "Healthcare & Wellness": 8,
    "Real Estate & Property": 8,
    "Retail & E-Commerce": 6,
    "Manufacturing & Logistics": 6,
    "Other": 5,
}

TEAM_SIZE_SCORES = {
    "Just me": 5,
    "2-10": 8,
    "11-50": 12,
    "51-200": 15,
    "200+": 15,
}

# Multi-select: 6 pts each, cap at 30
AI_TOOLS_OPTIONS = [
    "ChatGPT / Claude / AI Assistants",
    "AI-powered CRM (HubSpot AI, Salesforce Einstein)",
    "Email/marketing automation (Mailchimp, Klaviyo)",
    "Workflow automation (Zapier, Make, Power Automate)",
    "AI code/data tools (Copilot, custom scripts)",
]
AI_TOOLS_PTS_EACH = 6
AI_TOOLS_CAP = 30

# Pain point: multi-select now. 5 pts each, cap 20. "Pretty efficient" = 10 solo.
PAIN_POINT_PTS_EACH = 5
PAIN_POINT_CAP = 20
PAIN_POINT_NONE_VALUE = "We're pretty efficient already"
PAIN_POINT_NONE_PTS = 10

# AI goal: multi-select. 6 pts each, cap 25. "Just exploring" = 10 solo.
AI_GOAL_PTS_EACH = 6
AI_GOAL_CAP = 25
AI_GOAL_NONE_VALUE = "Just exploring / curious"
AI_GOAL_NONE_PTS = 10

# ---------------------------------------------------------------------------
# Readiness Levels
# ---------------------------------------------------------------------------

READINESS_LEVELS = [
    {"min": 0, "max": 30, "level": "Explorer", "color": "#8A8A96"},
    {"min": 31, "max": 60, "level": "Builder", "color": "#00D4AA"},
    {"min": 61, "max": 85, "level": "Optimizer", "color": "#00F5C4"},
    {"min": 86, "max": 100, "level": "Leader", "color": "#FFD700"},
]

# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------

SHEET_TITLE = "Ledger.AI Assessments"
SHEET_TAB = "ASSESSMENTS"

INTAKE_HEADERS = [
    "Timestamp",
    "Name",
    "Email",
    "Company",
    "Score",
    "Level",
    "Industry",
    "Team Size",
    "AI Tools",
    "Pain Point",
    "AI Goal",
    "Booked",
    "Insight",
]

# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------

CALENDAR_BOOKING_URL = (
    "https://calendar.google.com/calendar/u/0/appointments/"
    "schedules/AcZssZ0XciQbDe7_Ych-_xz1QP5mPqUXkIZ8mWjbQFKCJxY4TGdOR51h_8Srbg753dKn46oMQ-8T8d_F"
)
