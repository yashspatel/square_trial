const statusEl = document.getElementById("status");
const refreshBtn = document.getElementById("refresh");

const locName = document.getElementById("locName");
const locId = document.getElementById("locId");
const catalogCount = document.getElementById("catalogCount");
const teamCount = document.getElementById("teamCount");

const catalogBody = document.getElementById("catalogBody");
const teamBody = document.getElementById("teamBody");
const ordersBody = document.getElementById("ordersBody");

function esc(s) {
  return String(s ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function money(v, cur) {
  if (v === null || v === undefined) return "—";
  return `${cur || "USD"} $${Number(v).toFixed(2)}`;
}

function setStatus(text, type = "info") {
  statusEl.textContent = text;
  statusEl.className = "mb-4 rounded-xl border p-3 text-sm " + (
    type === "ok" ? "bg-emerald-50 border-emerald-200 text-emerald-700" :
      type === "err" ? "bg-red-50 border-red-200 text-red-700" :
        "bg-white border-slate-200 text-slate-600"
  );
}

function fillOrEmpty(tbody, html, cols) {
  tbody.innerHTML = html || `<tr><td class="py-3 text-slate-500" colspan="${cols}">No data</td></tr>`;
}

async function load() {
  setStatus("Loading Square data…", "info");
  try {
    const res = await fetch("/api/summary");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    locName.textContent = data.primary_location?.name || "—";
    locId.textContent = data.primary_location?.id || "—";

    catalogCount.textContent = data.catalog_items?.length ?? 0;
    teamCount.textContent = data.team_members?.length ?? 0;

    // catalog
    const catRows = (data.catalog_items || []).map(i => `
      <tr class="border-t">
        <td class="py-2 pr-4 font-medium">${esc(i.name)}</td>
        <td class="py-2 pr-4">${money(i.price, i.currency)}</td>
        <td class="py-2 pr-4 font-mono text-xs">${esc(i.id)}</td>
        <td class="py-2 pr-4 font-mono text-xs">${esc(i.variation_id)}</td>
      </tr>
    `).join("");
    fillOrEmpty(catalogBody, catRows, 4);

    // team
    const teamRows = (data.team_members || []).map(m => `
      <tr class="border-t">
        <td class="py-2 pr-4 font-medium">${esc(m.name)}</td>
        <td class="py-2 pr-4">${esc(m.status)}</td>
        <td class="py-2 pr-4">${m.wage_per_hour != null ? money(m.wage_per_hour, m.currency) + "/hr" : "—"}</td>
        <td class="py-2 pr-4">${esc(m.email || "—")}</td>
      </tr>
    `).join("");
    fillOrEmpty(teamBody, teamRows, 4);

    // orders
    const orderRows = (data.orders || []).map(o => `
      <tr class="border-t">
        <td class="py-2 pr-4">${esc(o.created_at || "—")}</td>
        <td class="py-2 pr-4">${esc(o.state || "—")}</td>
        <td class="py-2 pr-4">${money(o.total, o.currency)}</td>
        <td class="py-2 pr-4 font-mono text-xs">${esc(o.id)}</td>
      </tr>
    `).join("");
    fillOrEmpty(ordersBody, orderRows, 4);

    setStatus("Loaded successfully. Prices/wages normalized from cents → dollars.", "ok");
  } catch (e) {
    setStatus(`Failed to load: ${e.message}`, "err");
  }
}

refreshBtn.addEventListener("click", load);
load();
