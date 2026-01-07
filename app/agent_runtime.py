import os
from typing import List, Dict

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.tools import ToolException

from .mcp_client import build_square_mcp_client


BASE_SYSTEM = """
You are a Square Sandbox assistant connected through MCP, running inside a web app UI.

IMPORTANT UI CAPABILITY:
- This UI CAN display charts automatically if (and only if) you include a Chart.js config JSON wrapped EXACTLY like:
<CHART_CONFIG>
{ ... valid JSON ... }
</CHART_CONFIG>
- Therefore: NEVER say "I can't display charts" or "copy this config to render". The UI renders it for the user.

Tool rules:
- Tool methods are strict. If a tool call fails and shows "Available methods", pick from that list and retry.
- Orders search requires location_ids. If missing, call locations.list first.

Money rules:
- Square money fields are in cents (amount=3600 means $36.00). Convert to dollars in display.

Wage rules (CRITICAL — no guessing):
- Wage data is hourly_rate (money) in team member wage_setting/job_assignments.
- NEVER invent weekly/monthly salary unless a tool response explicitly provides it.
- For salary/wage/pay/rate questions:
  1) team.searchMembers (use name/context)
  2) team.getWageSetting if needed
  3) report hourly_rate.amount/100 as $/hr
  4) if missing, say not available in Square for that member.

Visualization rule (CRITICAL):
- If user asks for any chart/graph/plot/visualization OR it would help:
  1) Fetch needed data via tools.
  2) Reply briefly AND include <CHART_CONFIG> JSON.
- If user asks for "labels inside" on pie/doughnut:
  - Use Chart.js plugin "datalabels" via options.plugins.datalabels (JSON only).
"""

READ_ONLY_POLICY = """
MODE: READ-ONLY
- You may READ data and answer questions.
- Do NOT perform create/update/delete actions.
- If user asks to change data, tell them to use Approve/Reject in the UI.
"""

WRITE_ALLOWED_POLICY = """
MODE: WRITES ENABLED (APPROVED)
- The user already approved this action via the UI Approve button.
- Do NOT ask for confirmation.
- Execute the requested create/update/delete using tools.
- After writing, fetch and show the updated result briefly.
"""


async def _get_agent():
    client = build_square_mcp_client()
    tools = await client.get_tools()
    model = ChatOpenAI(model=os.environ.get("CHAT_MODEL", "gpt-4.1"))
    agent = create_agent(model, tools)
    return agent, client


def _looks_like_wage_question(messages: List[Dict[str, str]]) -> bool:
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = (m.get("content") or "").lower()
            break
    keywords = ["wage", "salary", "pay", "rate", "per hour", "/hr", "hourly", "weekly", "per week"]
    return any(k in last_user for k in keywords)


def _looks_like_chart_request(messages: List[Dict[str, str]]) -> bool:
    # Light check (not hardcoding chart type, just detecting chart intent)
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = (m.get("content") or "").lower()
            break

    # also treat "show me" as a chart request if recent assistant mentioned chart/graph
    if last_user.strip() in ["show me", "show", "display it", "render it"]:
        for m in reversed(messages[:-1]):
            if m.get("role") == "assistant":
                t = (m.get("content") or "").lower()
                if "chart" in t or "graph" in t or "<chart_config>" in t:
                    return True

    keywords = ["chart", "graph", "plot", "visualize", "visualisation", "visualization", "pie", "bar", "line"]
    return any(k in last_user for k in keywords)


def _has_chart_config(text: str) -> bool:
    t = text or ""
    return "<CHART_CONFIG>" in t and "</CHART_CONFIG>" in t


def _contains_weekly_salary_hallucination(text: str) -> bool:
    t = (text or "").lower()
    return ("per week" in t or "/week" in t or "weekly" in t) and ("tool" not in t)


async def run_agent_turn(messages: List[Dict[str, str]], allow_writes: bool) -> str:
    agent, client = await _get_agent()

    scratch = [
        {"role": "system", "content": BASE_SYSTEM},
        {"role": "system", "content": WRITE_ALLOWED_POLICY if allow_writes else READ_ONLY_POLICY},
        *list(messages),
    ]

    max_attempts = 4

    try:
        for attempt in range(1, max_attempts + 1):
            try:
                result = await agent.ainvoke({"messages": scratch})
                answer = result["messages"][-1].content

                # Wage hallucination guard
                if _looks_like_wage_question(messages) and _contains_weekly_salary_hallucination(answer):
                    scratch.append({
                        "role": "system",
                        "content": (
                            "Your previous answer invented weekly salary. Not allowed.\n"
                            "Retry: fetch wage_setting/hourly_rate via team.searchMembers and team.getWageSetting.\n"
                            "Return $/hr (amount/100). If missing, say not available."
                        )
                    })
                    continue

                # Chart omission guard
                if _looks_like_chart_request(messages) and not _has_chart_config(answer):
                    scratch.append({
                        "role": "system",
                        "content": (
                            "The user asked for a chart. You MUST include a valid Chart.js JSON config wrapped in "
                            "<CHART_CONFIG>...</CHART_CONFIG>. Do NOT say you can't display charts. Retry now."
                        )
                    })
                    continue

                return answer

            except ToolException as e:
                scratch.append({
                    "role": "system",
                    "content": (
                        f"Tool error (attempt {attempt}/{max_attempts}).\n\n{str(e)}\n\n"
                        "Recover by using only valid methods shown and retry."
                    ),
                })

        return "I couldn't complete the request after retries. Try rephrasing the question."

    finally:
        try:
            if hasattr(client, "aclose"):
                await client.aclose()
            elif hasattr(client, "close"):
                maybe = client.close()
                if hasattr(maybe, "__await__"):
                    await maybe
        except Exception:
            pass
