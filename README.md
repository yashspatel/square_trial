## Project Scope — Square AI Agent (MCP + LangGraph)

### What this project is
- A **ChatGPT-like web dashboard** for interacting with a **Square Sandbox developer account** using **Square MCP (Model Context Protocol)** tools.
- Built with **FastAPI** (backend), **LangGraph/LangChain agent** (reasoning + tool calling), and a **web chat UI** (HTML/JS).
- Designed for **natural-language questions and actions** over Square data.

---

### Key capabilities
- **Read (Q&A / Insights)**
  - Ask questions like: “How many items are in my menu?”, “Who is the cook?”, “Show wages per hour.”
  - Pulls data using MCP tools (example services):
    - `locations`
    - `catalog` (menu items + variations/prices)
    - `team` (members, jobs, wage settings)
    - `orders` (when available)

- **Write (Create/Update/Delete) with safety**
  - User can request actions like:
    - Add/remove/edit catalog items
    - Add/edit team members and roles/jobs
    - Update wage settings (if supported by tools)
  - **All writes require UI approval** via **Approve / Reject** buttons.

- **Charts / Visualizations**
  - User can ask for any chart (bar, pie, line, etc.) or the assistant chooses the best chart for the data.
  - UI renders charts automatically when the assistant returns a Chart.js config wrapped in:
    ```text
    <CHART_CONFIG>
    {...valid JSON...}
    </CHART_CONFIG>
    ```
  - Supports labels inside pie/doughnut using `chartjs-plugin-datalabels`.

---

### Non-negotiable rules (project constraints)
- **No hard-coded workflows** for specific requests:
  - The agent decides which tools to call and can loop tool calls until it has enough information.
- **LLM intent routing (not keyword routing)**:
  - Each user message is classified as: `read` / `write` / `clear` / `unknown`.
  - `write` ⇒ requires approval; `read` ⇒ responds immediately.
- **No extra “CONFIRM” messages**:
  - Once the user clicks **Approve**, the write must execute without asking for additional confirmation.
- **Data correctness**
  - Money fields from Square are in cents (`amount=3600` ⇒ `$36.00`) and must be displayed as `amount/100`.
  - Wage must come from Square wage settings (`hourly_rate`) and **must not be guessed** (no weekly/monthly salary hallucinations).
- **Charts must render**
  - The assistant must not say “I can’t display charts.”
  - For chart requests (or best-fit visualization), it must output `<CHART_CONFIG>` so the UI can render it.

---

### UX requirements
- Chat interface similar to ChatGPT:
  - Message bubbles, enter-to-send, clear chat
  - Friendly “processing” messages instead of just “...”
- Approve / Reject controls appear only when a write action is pending.
- After writes, the assistant fetches updated data and summarizes what changed.

---

### Backend endpoints (high level)
- `GET /chat` — chat UI page
- `POST /api/chat` — main chat endpoint (routes intent and runs agent)
- `POST /api/chat/approve` — executes pending write request (writes enabled)
- `POST /api/chat/reject` — cancels pending write request
- `GET /api/summary` — returns a JSON summary of current Square sandbox state (locations, catalog, team, etc.)

---

### Tech stack
- **FastAPI** (backend API + server)
- **LangGraph / LangChain** (agent orchestration)
- **Square MCP Server** via stdio (sandbox)
- **Chart.js** (+ `chartjs-plugin-datalabels`) for charts
- **HTML + JavaScript** for the chat UI

---

### Out of scope (for now)
- Production auth/multi-tenant security (sandbox-focused)
- Storing history in a database (currently session/in-memory oriented)
- Payroll/scheduling integrations beyond what Square MCP exposes
