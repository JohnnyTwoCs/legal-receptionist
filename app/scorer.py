"""
Scoring engine for the Ledger.AI AI Readiness Assessment.

calculate_score() — deterministic score from quiz answers
generate_insight() — Claude-powered personalized 2-3 sentence insight
"""

import os
from app.config import (
    INDUSTRY_SCORES,
    TEAM_SIZE_SCORES,
    AI_TOOLS_PTS_EACH,
    AI_TOOLS_CAP,
    PAIN_POINT_SCORES,
    AI_GOAL_SCORES,
    READINESS_LEVELS,
)


def calculate_score(answers):
    """
    Calculate AI Readiness Score from quiz answers.

    Args:
        answers: dict with keys: industry, team_size, ai_tools (list), pain_point, ai_goal

    Returns:
        dict with: score, level, level_color, breakdown
    """
    breakdown = {}

    # Industry (0-10)
    breakdown["industry"] = INDUSTRY_SCORES.get(answers.get("industry", ""), 5)

    # Team size (0-15)
    breakdown["team_size"] = TEAM_SIZE_SCORES.get(answers.get("team_size", ""), 5)

    # AI tools (0-30, 6 pts each)
    tools = answers.get("ai_tools", [])
    if isinstance(tools, str):
        tools = [tools]
    tools_score = len(tools) * AI_TOOLS_PTS_EACH
    breakdown["ai_tools"] = min(tools_score, AI_TOOLS_CAP)

    # Pain point (0-20)
    breakdown["pain_point"] = PAIN_POINT_SCORES.get(answers.get("pain_point", ""), 15)

    # AI goal (0-25)
    breakdown["ai_goal"] = AI_GOAL_SCORES.get(answers.get("ai_goal", ""), 15)

    score = sum(breakdown.values())
    score = max(0, min(100, score))

    # Determine level
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
    """
    Generate a personalized 2-3 sentence insight using Claude.

    Returns the insight string, or a fallback if the API call fails.
    """
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

        tools_str = ", ".join(answers.get("ai_tools", [])) or "none"

        prompt = f"""Write a 2-3 sentence personalized insight for a business prospect who just completed an AI readiness assessment. Be direct, confident, and specific to their situation. No fluff, no generic advice.

Their answers:
- Industry: {answers.get('industry', 'Unknown')}
- Team size: {answers.get('team_size', 'Unknown')}
- AI tools currently using: {tools_str}
- Biggest time sink: {answers.get('pain_point', 'Unknown')}
- #1 AI goal: {answers.get('ai_goal', 'Unknown')}
- Score: {score}/100 (Level: {level})

Rules:
- Address their specific pain point and industry
- Reference their current tool usage (or lack of it)
- End with a forward-looking statement that makes them want to book a call
- Never use dashes, use commas or semicolons instead
- Keep it under 50 words
- Sound like a sharp consultant, not a chatbot"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text.strip()

    except Exception as e:
        print(f"[Scorer] Claude insight failed: {e}", flush=True)
        return fallback_insights.get(level, fallback_insights["Builder"])
