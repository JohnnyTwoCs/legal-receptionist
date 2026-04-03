"""
Scoring engine for the Ledger.AI AI Readiness Assessment.

calculate_score() — deterministic score from quiz answers
generate_insight() — Claude-powered personalized 2-3 sentence insight
"""

from app.config import (
    INDUSTRY_SCORES,
    TEAM_SIZE_SCORES,
    AI_TOOLS_PTS_EACH,
    AI_TOOLS_CAP,
    PAIN_POINT_PTS_EACH,
    PAIN_POINT_CAP,
    PAIN_POINT_NONE_VALUE,
    PAIN_POINT_NONE_PTS,
    AI_GOAL_PTS_EACH,
    AI_GOAL_CAP,
    AI_GOAL_NONE_VALUE,
    AI_GOAL_NONE_PTS,
    READINESS_LEVELS,
)


def _to_list(val):
    """Normalize a value to a list (handles str, list, or None)."""
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    return list(val)


def calculate_score(answers):
    """
    Calculate AI Readiness Score from quiz answers.

    Returns dict with: score, level, level_color, breakdown
    """
    breakdown = {}

    # Industry (0-10)
    industry = answers.get("industry", "")
    breakdown["industry"] = INDUSTRY_SCORES.get(industry, 5)

    # Team size (0-15)
    breakdown["team_size"] = TEAM_SIZE_SCORES.get(answers.get("team_size", ""), 5)

    # AI tools — multi-select, 6 pts each, cap 30
    tools = _to_list(answers.get("ai_tools"))
    tools = [t for t in tools if t and t != "None yet"]
    breakdown["ai_tools"] = min(len(tools) * AI_TOOLS_PTS_EACH, AI_TOOLS_CAP)

    # Pain point — multi-select, 5 pts each, cap 20. "Pretty efficient" = 10 solo.
    pain = _to_list(answers.get("pain_point"))
    if PAIN_POINT_NONE_VALUE in pain or (len(pain) == 1 and pain[0] == PAIN_POINT_NONE_VALUE):
        breakdown["pain_point"] = PAIN_POINT_NONE_PTS
    else:
        pain = [p for p in pain if p and p != PAIN_POINT_NONE_VALUE]
        breakdown["pain_point"] = min(len(pain) * PAIN_POINT_PTS_EACH, PAIN_POINT_CAP)

    # AI goal — multi-select, 6 pts each, cap 25. "Just exploring" = 10 solo.
    goals = _to_list(answers.get("ai_goal"))
    if AI_GOAL_NONE_VALUE in goals or (len(goals) == 1 and goals[0] == AI_GOAL_NONE_VALUE):
        breakdown["ai_goal"] = AI_GOAL_NONE_PTS
    else:
        goals = [g for g in goals if g and g != AI_GOAL_NONE_VALUE]
        breakdown["ai_goal"] = min(len(goals) * AI_GOAL_PTS_EACH, AI_GOAL_CAP)

    score = max(0, min(100, sum(breakdown.values())))

    level_info = READINESS_LEVELS[0]
    for lvl in READINESS_LEVELS:
        if lvl["min"] <= score <= lvl["max"]:
            level_info = lvl
            break

    return {
        "score": score,
        "level": level_info["level"],
        "level_color": level_info["color"],
        "breakdown": breakdown,
    }


def generate_insight(answers, score, level):
    """Generate a personalized 2-3 sentence insight using Claude."""
    fallback_insights = {
        "Explorer": (
            "You're at the starting line, and that's exciting. A quick discovery call "
            "will map out your first quick wins and show you exactly where AI can "
            "start saving you time immediately."
        ),
        "Builder": (
            "You've got the foundation in place. The right automations could "
            "multiply your output without adding headcount. Let's identify the "
            "2-3 moves that will have the biggest impact."
        ),
        "Optimizer": (
            "You're already ahead of most businesses your size. The gap between "
            "where you are and where you could be is smaller than you think, "
            "but the ROI on closing it is massive."
        ),
        "Leader": (
            "You're in the top tier. At this stage, the wins come from strategic "
            "AI integration across your operation, not just individual tools. "
            "Let's talk about scaling what's working."
        ),
    }

    try:
        import anthropic
        client = anthropic.Anthropic()

        tools = _to_list(answers.get("ai_tools"))
        tools_str = ", ".join(t for t in tools if t != "None yet") or "none"

        pain = _to_list(answers.get("pain_point"))
        pain_str = ", ".join(pain) if pain else "not specified"

        goals = _to_list(answers.get("ai_goal"))
        goals_str = ", ".join(goals) if goals else "not specified"

        prompt = f"""Write a 2-3 sentence personalized insight for a business prospect who just completed an AI readiness assessment. Be direct, confident, and specific to their situation. No fluff, no generic advice.

Their answers:
- Industry: {answers.get('industry', 'Unknown')}
- Team size: {answers.get('team_size', 'Unknown')}
- AI tools currently using: {tools_str}
- Biggest time sinks: {pain_str}
- AI goals: {goals_str}
- Score: {score}/100 (Level: {level})

Rules:
- Address their specific pain points and industry
- Reference their current tool usage (or lack of it)
- End with a forward-looking statement that makes them want to book a call
- Never use dashes; use commas or semicolons instead
- Keep it under 50 words
- Sound like a sharp consultant, not a chatbot
- We help people optimize and maximize their team's value, never mention reducing headcount"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text.strip()

    except Exception as e:
        print(f"[Scorer] Claude insight failed: {e}", flush=True)
        return fallback_insights.get(level, fallback_insights["Builder"])
