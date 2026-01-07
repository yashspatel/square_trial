from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from .mcp_client import build_square_mcp_client


SYSTEM_INSTRUCTIONS = (
    "You are a Square Sandbox assistant.\n"
    "- Prefer read-only calls.\n"
    "- If a request would create/update/delete anything, ask for confirmation first.\n"
    "- When unsure, use get_service_info and get_type_info before make_api_request.\n"
)


async def run_agent_demo():
    client = build_square_mcp_client()
    tools = await client.get_tools()

    model = ChatOpenAI(model="gpt-4.1")

    # ---- FIX: your create_agent does not accept state_modifier
    # Try system_prompt first; if that fails, try prompt (below).
    try:
        agent = create_agent(model, tools, system_prompt=SYSTEM_INSTRUCTIONS)
    except TypeError:
        agent = create_agent(model, tools, prompt=SYSTEM_INSTRUCTIONS)

    prompts = [
        "List my Square sandbox locations (id, name, status).",
        "Show the 5 most recent orders (id, created_at, state, total_money).",
        "List 5 customers (id, given_name, family_name, email_address) if available.",
    ]

    for p in prompts:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": p}]})
        print("\nUSER:", p)
        print("ASSISTANT:", result["messages"][-1].content)

    await client.close()
