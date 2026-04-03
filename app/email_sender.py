"""
Confirmation email sender for Ledger.AI Onboarding Assistant.

Sends a branded HTML email with assessment results and call prep info.
"""

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SENDER = "jon@getledger.net"


def send_confirmation(to_email, name, data):
    """
    Send a confirmation email with assessment summary and prep info.

    Args:
        to_email: recipient email
        name: recipient's name
        data: dict with score, level, insight, industry, team_size,
              ai_tools, pain_point, ai_goal, company, source (text/voice)
    """
    try:
        from app.google_api import get_gmail_service
        service = get_gmail_service()
        if not service:
            print("[Email] Gmail service not available", flush=True)
            return False

        score = data.get("score", "N/A")
        level = data.get("level", "N/A")
        insight = data.get("insight", "")
        company = data.get("company", "")
        industry = data.get("industry", "N/A")
        team_size = data.get("team_size", "N/A")
        source = data.get("source", "text")

        tools = data.get("ai_tools", [])
        if isinstance(tools, list):
            tools_str = ", ".join(tools) if tools else "None currently"
        else:
            tools_str = tools or "None currently"

        pain = data.get("pain_point", "")
        if isinstance(pain, list):
            pain_str = ", ".join(pain)
        else:
            pain_str = pain or "N/A"

        goals = data.get("ai_goal", "")
        if isinstance(goals, list):
            goals_str = ", ".join(goals)
        else:
            goals_str = goals or "N/A"

        mode_label = "voice conversation" if source == "voice" else "online assessment"

        subject = f"Your AI Readiness Results | Ledger.AI"

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0A0A0B;font-family:'Helvetica Neue',Arial,sans-serif;color:#F0F0F2;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0A0A0B;padding:40px 20px;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">

<!-- Header -->
<tr><td style="padding-bottom:32px;text-align:center;">
  <span style="font-size:20px;font-weight:800;color:#F0F0F2;">Ledger</span><span style="font-size:20px;font-weight:800;color:#00D4AA;">.</span><span style="font-size:20px;font-weight:800;color:#F0F0F2;">AI</span>
</td></tr>

<!-- Score Card -->
<tr><td style="background:#1C1C20;border:1px solid #2A2A30;border-radius:12px;padding:32px;text-align:center;">
  <div style="font-size:14px;color:#8A8A96;margin-bottom:8px;">Your AI Readiness Score</div>
  <div style="font-size:56px;font-weight:800;color:#00D4AA;line-height:1;">{score}</div>
  <div style="font-size:14px;color:#55555F;margin-bottom:16px;">/ 100</div>
  <div style="display:inline-block;background:rgba(0,212,170,0.1);border:1px solid rgba(0,212,170,0.2);border-radius:16px;padding:4px 16px;font-size:14px;font-weight:700;color:#00D4AA;">{level}</div>
</td></tr>

<!-- Insight -->
<tr><td style="padding:24px 0;">
  <div style="font-size:13px;color:#8A8A96;margin-bottom:8px;">PERSONALIZED INSIGHT</div>
  <div style="font-size:15px;color:#F0F0F2;line-height:1.6;">{insight}</div>
</td></tr>

<!-- Assessment Summary -->
<tr><td style="background:#1C1C20;border:1px solid #2A2A30;border-radius:12px;padding:24px;">
  <div style="font-size:13px;color:#00D4AA;font-weight:600;margin-bottom:16px;">YOUR ASSESSMENT SUMMARY</div>
  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;">
    <tr><td style="color:#8A8A96;padding:6px 0;">Industry</td><td style="color:#F0F0F2;text-align:right;padding:6px 0;">{industry}</td></tr>
    <tr><td style="color:#8A8A96;padding:6px 0;">Team Size</td><td style="color:#F0F0F2;text-align:right;padding:6px 0;">{team_size}</td></tr>
    <tr><td style="color:#8A8A96;padding:6px 0;">AI Tools</td><td style="color:#F0F0F2;text-align:right;padding:6px 0;">{tools_str}</td></tr>
    <tr><td style="color:#8A8A96;padding:6px 0;">Biggest Time Sinks</td><td style="color:#F0F0F2;text-align:right;padding:6px 0;">{pain_str}</td></tr>
    <tr><td style="color:#8A8A96;padding:6px 0;">AI Goals</td><td style="color:#F0F0F2;text-align:right;padding:6px 0;">{goals_str}</td></tr>
    <tr><td style="color:#8A8A96;padding:6px 0;">Assessment Mode</td><td style="color:#F0F0F2;text-align:right;padding:6px 0;">{mode_label.title()}</td></tr>
  </table>
</td></tr>

<!-- Prep Section -->
<tr><td style="padding:24px 0;">
  <div style="font-size:13px;color:#00D4AA;font-weight:600;margin-bottom:12px;">PREP FOR YOUR DISCOVERY CALL</div>
  <div style="font-size:14px;color:#F0F0F2;line-height:1.7;">
    To make the most of your 30 minutes with Jon, have these ready:<br><br>
    1. A quick list of your top 3 most repetitive tasks or workflows<br>
    2. Any tools or software you currently use daily<br>
    3. A rough idea of how many hours per week your team spends on manual work<br>
    4. Any specific outcomes you're hoping to achieve (cost savings, speed, accuracy)<br><br>
    Jon will have reviewed your assessment results before the call, so you won't need to repeat anything from today's {mode_label}.
  </div>
</td></tr>

<!-- Footer -->
<tr><td style="padding-top:24px;border-top:1px solid #2A2A30;text-align:center;">
  <div style="font-size:12px;color:#55555F;line-height:1.6;">
    Ledger.AI | <a href="https://getledger.net" style="color:#00D4AA;text-decoration:none;">getledger.net</a><br>
    Stop losing hours. Start building leverage.
  </div>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

        msg = MIMEMultipart("alternative")
        msg["to"] = to_email
        msg["from"] = SENDER
        msg["subject"] = subject

        # Plain text fallback
        plain = f"""Hi {name},

Thanks for completing your AI Readiness Assessment with Ledger.AI!

YOUR SCORE: {score}/100 ({level})

{insight}

ASSESSMENT SUMMARY:
- Industry: {industry}
- Team Size: {team_size}
- AI Tools: {tools_str}
- Time Sinks: {pain_str}
- AI Goals: {goals_str}

PREP FOR YOUR DISCOVERY CALL:
To make the most of your 30 minutes with Jon, have these ready:
1. A quick list of your top 3 most repetitive tasks or workflows
2. Any tools or software you currently use daily
3. A rough idea of how many hours per week your team spends on manual work
4. Any specific outcomes you're hoping to achieve (cost savings, speed, accuracy)

Jon will have reviewed your results before the call, so you won't need to repeat anything.

Ledger.AI | getledger.net
Stop losing hours. Start building leverage.
"""

        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()

        print(f"[Email] Confirmation sent to {to_email}", flush=True)
        return True

    except Exception as e:
        print(f"[Email] Send failed: {e}", flush=True)
        return False
