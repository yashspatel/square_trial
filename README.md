# square_trial

Product scope

ChatGPT-like web chat UI for Square Sandbox operations (read + write).

Supports natural language questions + actions on:

Locations

Catalog (menu items + prices)

Team members (roles/jobs + wages)

Orders (when available)

Core behaviors

LLM intent routing: classify each message as read / write / clear / unknown.

Write requests require explicit Approve/Reject UI gating.

Approved writes execute automatically (no extra “CONFIRM”).

Agent can loop tool calls until it can answer.

Data correctness rules

Convert all money from cents to dollars (amount/100).

Wage must come from Square wage_setting/hourly_rate; never infer weekly/monthly salary.

If data is missing, respond “not available” and request minimal missing identifiers.

Visualization scope

Agent selects best chart type for the data/request (no hardcoding).

For any chart request (or best visualization), agent must output Chart.js JSON inside <CHART_CONFIG>...</CHART_CONFIG>.

Support datalabels for inside-slice labels on pie/doughnut.

UX scope

Friendly progress/status text while waiting (not “…”).

Clear button to reset chat state.

Approve/Reject buttons appear only when needed.

Technical scope

FastAPI endpoints: /api/chat, /api/chat/approve, /api/chat/reject, /api/summary.

MCP client connects to Square MCP server (stdio, sandbox access token).

Session-based chat history + pending action store.

Non-goals / constraints

No “keyword hardcoding” for deciding intent or chart type.

Do not frequently rename files or restructure folders.

Do not claim capabilities not backed by tools (no hallucinated salary/week, etc.).
