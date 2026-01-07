import json
import os
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI


ROUTER_SYSTEM = """
You are an intent router for a Square Sandbox assistant.

Classify the user's message into one of:
- "clear": user wants to clear/reset chat/history
- "write": user wants to CREATE/UPDATE/DELETE Square data (catalog items, team members, jobs, wages, etc.)
- "read": user wants to fetch/see/analyze data (questions, summaries, charts, reports) without changing Square data
- "unknown": unclear

Return ONLY valid JSON with this schema:
{
  "intent": "clear" | "write" | "read" | "unknown",
  "needs_confirm": true | false,
  "reason": "short reason",
  "normalized_request": "rewrite the user request clearly (1 sentence)"
}

Rules:
- If intent == "write" -> needs_confirm must be true.
- If intent == "read" -> needs_confirm must be false.
- Charts/graphs/visualizations are ALWAYS "read" unless user explicitly asks to modify Square data too.
- If unclear whether it's read or write, choose "unknown" with needs_confirm false.
"""


def _safe_json_loads(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    # strip common markdown wrappers
    if text.startswith("```"):
        text = text.strip("`")
    # best effort find first/last braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


async def route_intent(user_text: str, history: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
    """
    Uses the LLM to decide if a message is read vs write (needs approval) vs clear.
    No keyword hardcoding required.
    """
    model = ChatOpenAI(
        model=os.environ.get("ROUTER_MODEL", os.environ.get("CHAT_MODEL", "gpt-4.1")),
        temperature=0,
    )

    # Provide tiny context if available (helps with "him", "the cook", etc.)
    context_snippet = ""
    if history:
        # last few turns only
        tail = history[-6:]
        context_snippet = "\n".join([f"{m.get('role','')}: {m.get('content','')}" for m in tail])

    user_prompt = {
        "role": "user",
        "content": f"User message: {user_text}\n\nRecent context:\n{context_snippet}".strip()
    }

    resp = await model.ainvoke([
        {"role": "system", "content": ROUTER_SYSTEM},
        user_prompt
    ])

    try:
        data = _safe_json_loads(resp.content)
    except Exception:
        # Conservative fallback: treat as read if router fails
        data = {
            "intent": "read",
            "needs_confirm": False,
            "reason": "Router parse failed; defaulting to read.",
            "normalized_request": user_text,
        }

    # sanitize
    intent = data.get("intent", "unknown")
    if intent not in ("clear", "write", "read", "unknown"):
        intent = "unknown"

    needs_confirm = bool(data.get("needs_confirm", False))
    if intent == "write":
        needs_confirm = True
    elif intent in ("read", "clear"):
        needs_confirm = False

    return {
        "intent": intent,
        "needs_confirm": needs_confirm,
        "reason": str(data.get("reason", ""))[:200],
        "normalized_request": str(data.get("normalized_request", user_text))[:500],
    }
