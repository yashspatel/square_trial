import os
import asyncio
from dotenv import load_dotenv

from .graph_agent import run_agent_demo
from .graph_workflow import run_workflow_demo


def main():
    load_dotenv()

    mode = (os.environ.get("MODE") or "agent").strip().lower()
    print(f"Running MODE={mode}")  # helpful debug

    if mode == "workflow":
        asyncio.run(run_workflow_demo())
    else:
        asyncio.run(run_agent_demo())


if __name__ == "__main__":
    main()
