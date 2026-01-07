const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");

const actionsEl = document.getElementById("actions");
const approveBtn = document.getElementById("approveBtn");
const rejectBtn = document.getElementById("rejectBtn");

const sessionId = localStorage.getItem("square_chat_session") || crypto.randomUUID();
localStorage.setItem("square_chat_session", sessionId);

// Register datalabels plugin if present
if (window.Chart && window.ChartDataLabels) {
    Chart.register(ChartDataLabels);
}

function esc(s) {
    return String(s ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function showActions(show) {
    actionsEl.classList.toggle("hidden", !show);
    actionsEl.classList.toggle("flex", show);
}

function addBubble(role, text) {
    const wrap = document.createElement("div");
    const isUser = role === "user";
    wrap.className = `flex ${isUser ? "justify-end" : "justify-start"}`;

    const bubble = document.createElement("div");
    bubble.className =
        `max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ` +
        (isUser ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-900");

    bubble.innerHTML = esc(text).replaceAll("\n", "<br/>");
    wrap.appendChild(bubble);

    chatEl.appendChild(wrap);
    chatEl.scrollTop = chatEl.scrollHeight;

    return bubble;
}

function extractChartConfig(text) {
    const startTag = "<CHART_CONFIG>";
    const endTag = "</CHART_CONFIG>";
    const start = text.indexOf(startTag);
    const end = text.indexOf(endTag);

    if (start === -1 || end === -1 || end <= start) {
        return { cleanText: text, config: null };
    }

    const jsonStr = text.slice(start + startTag.length, end).trim();
    let config = null;
    try {
        config = JSON.parse(jsonStr);
    } catch (e) {
        config = null;
    }

    const cleanText = (text.slice(0, start) + text.slice(end + endTag.length)).trim();
    return { cleanText, config };
}

// Generate colors if not provided
function ensureDatasetColors(config) {
    try {
        const ds = config?.data?.datasets;
        if (!Array.isArray(ds)) return;

        ds.forEach((d, idx) => {
            const needsBg = !("backgroundColor" in d);
            const needsBorder = !("borderColor" in d);

            const color = `hsl(${(idx * 57) % 360}, 70%, 55%)`;
            const bg = `hsla(${(idx * 57) % 360}, 70%, 55%, 0.35)`;

            if (needsBorder) d.borderColor = color;

            if (needsBg) {
                if (["pie", "doughnut", "polarArea"].includes(config.type)) {
                    const n = Array.isArray(config?.data?.labels) ? config.data.labels.length : 0;
                    d.backgroundColor = Array.from(
                        { length: n },
                        (_, i) => `hsla(${(i * 57) % 360}, 70%, 55%, 0.55)`
                    );
                    d.borderColor = Array.from(
                        { length: n },
                        (_, i) => `hsl(${(i * 57) % 360}, 70%, 45%)`
                    );
                } else {
                    d.backgroundColor = bg;
                }
            }
        });
    } catch (_) { }
}

function renderChartIntoBubble(bubbleDiv, chartConfig) {
    const wrap = document.createElement("div");
    wrap.className = "mt-3 bg-white rounded-xl border p-3";

    const canvas = document.createElement("canvas");
    wrap.appendChild(canvas);
    bubbleDiv.appendChild(wrap);

    ensureDatasetColors(chartConfig);

    // Defaults to make charts look decent
    chartConfig.options = chartConfig.options || {};
    if (!("responsive" in chartConfig.options)) chartConfig.options.responsive = true;
    if (!chartConfig.options.maintainAspectRatio) chartConfig.options.maintainAspectRatio = false;

    // For pie/doughnut, enable datalabels if user asked "labels inside"
    // The agent should set this in config, but this fallback helps.
    chartConfig.plugins = chartConfig.plugins || [];

    try {
        // Make the chart container a bit taller
        wrap.style.height = "360px";

        new Chart(canvas.getContext("2d"), chartConfig);
    } catch (e) {
        const err = document.createElement("div");
        err.className = "text-xs text-red-600 mt-2";
        err.textContent = "Failed to render chart (invalid Chart.js config).";
        wrap.appendChild(err);
    }
}

// Friendly progress logs while waiting (no backend changes needed)
function startFriendlyLogs(bubbleDiv, kind = "general") {
    const sequences = {
        general: [
            "Thinking…",
            "Fetching your Square data…",
            "Organizing results…",
            "Finalizing response…",
        ],
        chart: [
            "Fetching the data for your chart…",
            "Preparing labels and values…",
            "Building a chart configuration…",
            "Rendering the chart…",
        ],
        write: [
            "Reviewing requested changes…",
            "Preparing update request…",
            "Applying changes…",
            "Finalizing…",
        ],
    };

    const steps = sequences[kind] || sequences.general;
    let i = 0;

    bubbleDiv.innerHTML = esc(steps[0]);

    const id = setInterval(() => {
        i = (i + 1) % steps.length;
        bubbleDiv.innerHTML = esc(steps[i]);
    }, 900);

    return () => clearInterval(id);
}

function isChartPrompt(text) {
    const t = (text || "").toLowerCase();
    return ["chart", "graph", "plot", "visual", "visualize", "pie", "bar", "line"].some((k) =>
        t.includes(k)
    );
}

async function sendMessage(text) {
    addBubble("user", text);
    inputEl.value = "";
    sendBtn.disabled = true;

    const typingBubble = addBubble("assistant", "…");
    const stopLogs = startFriendlyLogs(typingBubble, isChartPrompt(text) ? "chart" : "general");

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, message: text }),
        });

        const data = await res.json();
        stopLogs();

        const { cleanText, config } = extractChartConfig(data.reply || "");
        typingBubble.innerHTML = esc(cleanText).replaceAll("\n", "<br/>");

        if (config && typeof config === "object") {
            renderChartIntoBubble(typingBubble, config);
        }

        showActions(!!data.needs_confirm);
    } catch (e) {
        stopLogs();
        typingBubble.innerHTML = `Error: ${esc(e.message)}`;
        showActions(false);
    } finally {
        sendBtn.disabled = false;
        inputEl.focus();
    }
}

sendBtn.addEventListener("click", () => {
    const text = inputEl.value.trim();
    if (text) sendMessage(text);
});

inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const text = inputEl.value.trim();
        if (text) sendMessage(text);
    }
});

approveBtn.addEventListener("click", async () => {
    showActions(false);
    addBubble("user", "✅ Approved");

    const typingBubble = addBubble("assistant", "Working…");
    const stopLogs = startFriendlyLogs(typingBubble, "write");

    try {
        const res = await fetch("/api/chat/approve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
        });

        const data = await res.json();
        stopLogs();

        const { cleanText, config } = extractChartConfig(data.reply || "");
        typingBubble.innerHTML = esc(cleanText).replaceAll("\n", "<br/>");

        if (config && typeof config === "object") {
            renderChartIntoBubble(typingBubble, config);
        }
    } catch (e) {
        stopLogs();
        typingBubble.innerHTML = `Error: ${esc(e.message)}`;
    }
});

rejectBtn.addEventListener("click", async () => {
    showActions(false);
    addBubble("user", "❌ Rejected");

    const typingBubble = addBubble("assistant", "Cancelling…");
    const stopLogs = startFriendlyLogs(typingBubble, "general");

    try {
        const res = await fetch("/api/chat/reject", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
        });

        const data = await res.json();
        stopLogs();
        typingBubble.innerHTML = esc(data.reply || "").replaceAll("\n", "<br/>");
    } catch (e) {
        stopLogs();
        typingBubble.innerHTML = `Error: ${esc(e.message)}`;
    }
});

clearBtn.addEventListener("click", async () => {
    await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: "/clear" }),
    });

    chatEl.innerHTML = "";
    showActions(false);
    addBubble("assistant", "Chat cleared. Ask me something about your Square sandbox.");
});

// greeting
addBubble(
    "assistant",
    "Hi! Ask me:\n" +
    "- Show a chart of catalog prices\n" +
    "- Visualize team wages\n" +
    "- Plot orders by day (if you have orders)\n" +
    "- Remove an item (Approve/Reject)\n"
);
