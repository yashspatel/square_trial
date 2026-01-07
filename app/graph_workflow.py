import json
import asyncio
from typing import Any, Dict, List, Optional

from langchain_core.tools import ToolException
from .mcp_client import build_square_mcp_client


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


def money_to_decimal(amount: Optional[int], currency: str = "USD") -> float:
    # Square returns smallest unit (USD cents). 400 => 4.00
    if amount is None:
        return 0.0
    return round(amount / 100.0, 2)


async def get_square_summary() -> Dict[str, Any]:
    client = build_square_mcp_client()
    tools = await client.get_tools()
    make_api = next((t for t in tools if t.name.endswith("make_api_request")), None)
    if make_api is None:
        raise RuntimeError("Could not find make_api_request tool from Square MCP server.")

    # 1) Locations
    loc_raw = await make_api.ainvoke({"service": "locations", "method": "list", "request": {}})
    locations = unwrap_mcp_json(loc_raw).get("locations", [])
    location_ids = [l.get("id") for l in locations if isinstance(l, dict) and l.get("id")]
    first_location_id = location_ids[0] if location_ids else None

    # 2) Catalog items
    cat_raw = await make_api.ainvoke({
        "service": "catalog",
        "method": "list",
        "request": {"types": "ITEM", "limit": 200},
    })
    catalog = unwrap_mcp_json(cat_raw).get("objects", [])

    catalog_items = []
    for obj in catalog:
        if obj.get("type") != "ITEM":
            continue
        item = obj.get("item_data", {})
        variations = item.get("variations", [])
        # show first variation price for simplicity (you can list all later)
        price = None
        currency = None
        if variations:
            vdata = variations[0].get("item_variation_data", {})
            pm = vdata.get("price_money", {})
            price = money_to_decimal(pm.get("amount"), pm.get("currency", "USD"))
            currency = pm.get("currency", "USD")

        catalog_items.append({
            "id": obj.get("id"),
            "name": item.get("name"),
            "price": price,
            "currency": currency,
            "variation_id": variations[0].get("id") if variations else None
        })

    # 3) Team members
    try:
        team_raw = await make_api.ainvoke({
            "service": "team",
            "method": "searchMembers",
            "request": {"limit": 200},
        })
        team_members = unwrap_mcp_json(team_raw).get("team_members", [])
    except ToolException:
        team_members = []

    team_out = []
    for tm in team_members:
        wage = None
        wage_currency = None
        jobs = tm.get("wage_setting", {}).get("job_assignments", [])
        for j in jobs:
            hr = j.get("hourly_rate")
            if hr:
                wage = money_to_decimal(hr.get("amount"), hr.get("currency", "USD"))
                wage_currency = hr.get("currency", "USD")
                break

        team_out.append({
            "id": tm.get("id"),
            "name": f"{tm.get('given_name','')} {tm.get('family_name','')}".strip(),
            "status": tm.get("status"),
            "email": tm.get("email_address"),
            "phone": tm.get("phone_number"),
            "wage_per_hour": wage,
            "currency": wage_currency,
            "assigned_locations": tm.get("assigned_locations", {}),
        })

    # 4) Orders (might be empty if you haven’t created any)
    orders_out = []
    if first_location_id:
        try:
            orders_raw = await make_api.ainvoke({
                "service": "orders",
                "method": "search",
                "request": {
                    "location_ids": [first_location_id],
                    "limit": 20,
                    "sort": {"sort_field": "CREATED_AT", "sort_order": "DESC"},
                },
            })
            orders = unwrap_mcp_json(orders_raw).get("orders", []) or []
            for o in orders:
                total = o.get("total_money", {})
                orders_out.append({
                    "id": o.get("id"),
                    "state": o.get("state"),
                    "created_at": o.get("created_at"),
                    "total": money_to_decimal(total.get("amount"), total.get("currency", "USD")),
                    "currency": total.get("currency", "USD"),
                })
        except ToolException:
            orders_out = []

    # close client safely (works across versions)
    try:
        if hasattr(client, "aclose"):
            await client.aclose()
        elif hasattr(client, "close"):
            maybe = client.close()
            if asyncio.iscoroutine(maybe):
                await maybe
    except Exception:
        pass

    return {
        "locations": locations,
        "catalog_items": catalog_items,
        "team_members": team_out,
        "orders": orders_out,
        "meta": {
            "location_ids": location_ids,
            "primary_location_id": first_location_id,
            "note": "Money amounts are normalized from cents to dollars.",
        }
    }
