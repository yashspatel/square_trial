import os
import json
import asyncio
import pathlib
from typing import Any, Dict, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .mcp_client import build_square_mcp_client
from .agent_runtime import run_agent_turn
from .intent_router import route_intent
from .memory_store import (
    get_history,
    append_message,
    clear_history,
    set_pending,
    get_pending,
    clear_pending,
)

app = FastAPI(title="Square MCP Dashboard + Agent")

WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web"
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


def unwrap_mcp_json(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except Exception:
            return {"raw": result}
    if isinstance(result, list):
        for block in result:
            if isinstance(block, dict) and block.get("type") == "text" and "text" in block:
                try:
                    return json.loads(block["text"])
                except Exception:
                    return {"raw": block.get("text")}
        return {"raw": result}
    return {"raw": result}


def money_to_decimal(money: Optional[dict]) -> Optional[float]:
    if not money:
        return None
    amt = money.get("amount")
    if amt is None:
        return None
    return round(amt / 100.0, 2)


@app.get("/", response_class=HTMLResponse)
def index():
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/chat", response_class=HTMLResponse)
def chat_page():
    return (WEB_DIR / "chat.html").read_text(encoding="utf-8")


@app.get("/api/summary")
async def get_summary():
    client = build_square_mcp_client()
    tools = await client.get_tools()
    make_api = next((t for t in tools if t.name.endswith("make_api_request")), None)
    if make_api is None:
        raise RuntimeError("make_api_request tool not found")

    try:
        loc_raw = await make_api.ainvoke({"service": "locations", "method": "list", "request": {}})
        loc = unwrap_mcp_json(loc_raw)
        locations = loc.get("locations", []) or []
        location_id = locations[0]["id"] if locations else None

        cat_raw = await make_api.ainvoke({
            "service": "catalog",
            "method": "list",
            "request": {"types": "ITEM", "limit": 200},
        })
        cat = unwrap_mcp_json(cat_raw)
        objects = cat.get("objects", []) or []

        catalog_items = []
        for obj in objects:
            if obj.get("type") != "ITEM":
                continue
            item = obj.get("item_data", {})
            variations = item.get("variations", [])
            first_var = variations[0] if variations else {}
            vdata = first_var.get("item_variation_data", {})
            price_money = vdata.get("price_money", {})

            catalog_items.append({
                "id": obj.get("id"),
                "name": item.get("name"),
                "variation_id": first_var.get("id"),
                "price": money_to_decimal(price_money),
                "currency": price_money.get("currency", "USD") if price_money else "USD",
            })

        team_raw = await make_api.ainvoke({
            "service": "team",
            "method": "searchMembers",
            "request": {"limit": 200},
        })
        team = unwrap_mcp_json(team_raw)
        members = team.get("team_members", []) or []

        team_members = []
        for tm in members:
            jobs = tm.get("wage_setting", {}).get("job_assignments", [])
            hourly_money = None
            for j in jobs:
                if j.get("hourly_rate"):
                    hourly_money = j.get("hourly_rate")
                    break

            team_members.append({
                "id": tm.get("id"),
                "name": f"{tm.get('given_name','')} {tm.get('family_name','')}".strip(),
                "status": tm.get("status"),
                "email": tm.get("email_address"),
                "phone": tm.get("phone_number"),
                "wage_per_hour": money_to_decimal(hourly_money),
                "currency": (hourly_money or {}).get("currency", "USD") if hourly_money else "USD",
            })

        return {
            "primary_location": {
                "id": location_id,
                "name": locations[0]["name"] if locations else None,
                "status": locations[0]["status"] if locations else None,
            },
            "locations": locations,
            "catalog_items": catalog_items,
            "team_members": team_members,
            "note": "Money values are normalized from cents to dollars (amount/100).",
        }

    finally:
        try:
            if hasattr(client, "aclose"):
                await client.aclose()
            elif hasattr(client, "close"):
                maybe = client.close()
                if asyncio.iscoroutine(maybe):
                    await maybe
        except Exception:
            pass


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    needs_confirm: bool = False
    pending_action_id: Optional[str] = None


class SessionOnly(BaseModel):
    session_id: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = req.session_id.strip()
    user_text = req.message.strip()

    # Always record user message
    append_message(session_id, "user", user_text)

    # Route intent using LLM (no hardcoded keywords)
    history = get_history(session_id)
    route = await route_intent(user_text, history=history)

    if route["intent"] == "clear" or user_text.lower() in ["/clear", "clear chat", "reset"]:
        clear_history(session_id)
        return ChatResponse(reply="✅ Cleared chat.", needs_confirm=False)

    if route["intent"] == "write" and route["needs_confirm"]:
        # Store the normalized request so approval executes something clean
        action_id = set_pending(session_id, route["normalized_request"])
        return ChatResponse(
            reply="I can do that. Click **Approve** to proceed or **Reject** to cancel.",
            needs_confirm=True,
            pending_action_id=action_id,
        )

    # Read / unknown: run read-only agent turn
    reply = await run_agent_turn(get_history(session_id), allow_writes=False)
    append_message(session_id, "assistant", reply)
    return ChatResponse(reply=reply, needs_confirm=False)


@app.post("/api/chat/approve", response_model=ChatResponse)
async def chat_approve(req: SessionOnly):
    session_id = req.session_id.strip()
    pending = get_pending(session_id)
    if not pending:
        return ChatResponse(reply="No pending action to approve.", needs_confirm=False)

    disallow = (os.environ.get("DISALLOW_WRITES", "true").lower() == "true")
    if disallow:
        return ChatResponse(
            reply="Writes are disabled (DISALLOW_WRITES=true). Set DISALLOW_WRITES=false in .env and restart.",
            needs_confirm=False,
        )

    user_request = pending["user_request"]
    clear_pending(session_id)

    # Execute with writes enabled
    append_message(session_id, "user", user_request)
    reply = await run_agent_turn(get_history(session_id), allow_writes=True)
    append_message(session_id, "assistant", reply)

    return ChatResponse(reply=reply, needs_confirm=False)


@app.post("/api/chat/reject", response_model=ChatResponse)
async def chat_reject(req: SessionOnly):
    session_id = req.session_id.strip()
    pending = get_pending(session_id)
    if not pending:
        return ChatResponse(reply="No pending action to reject.", needs_confirm=False)

    clear_pending(session_id)
    msg = "✅ Cancelled. No changes were made."
    append_message(session_id, "assistant", msg)
    return ChatResponse(reply=msg, needs_confirm=False)
