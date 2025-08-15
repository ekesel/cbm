from __future__ import annotations
import requests, json
from typing import List, Dict, Any, Optional
from django.conf import settings

def post_teams_card(webhook_url: str, payload: Dict[str, Any]) -> bool:
    """
    Send a MessageCard to Teams Incoming Webhook.
    """
    resp = requests.post(webhook_url, json=payload, timeout=(5, 15))
    try:
        resp.raise_for_status()
        return True
    except requests.HTTPError:
        return False

def remediation_card(board_name: str, summary: str, tickets: List[Dict[str, Any]], admin_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Build a compact MessageCard listing up to N tickets (grouped already).
    """
    facts = []
    for t in tickets:
        facts.append({"name": t["rule"], "value": f"{t['count']} issues"})

    text_lines = []
    for t in tickets:
        samples = ", ".join(t.get("samples", [])[:5])
        if samples:
            text_lines.append(f"**{t['rule']}** — e.g. {samples}")
    text = "\n".join(text_lines) if text_lines else "See Admin for details."

    card = {
      "@type": "MessageCard",
      "@context": "http://schema.org/extensions",
      "summary": summary,
      "themeColor": "E81123",  # Teams red
      "title": f"⚠️ Remediation Alerts — {board_name}",
      "sections": [
        {"activityTitle": summary, "facts": facts, "markdown": True},
        {"text": text, "markdown": True}
      ],
      "potentialAction": []
    }
    if admin_url:
        card["potentialAction"].append({
          "@type": "OpenUri", "name": "Open Admin",
          "targets": [{"os":"default","uri": admin_url}]
        })
    return card
