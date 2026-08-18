"use strict";

const allowedEvents = [
  "acknowledge", "start", "answer", "confirm", "continue",
  "handoff_acknowledged", "mock_success", "mock_failure", "finish", "end",
];
let sessionToken = "";
let runtime = null;
const byId = (id) => document.getElementById(id);

function render() {
  const spec = runtime.specification;
  const session = runtime.session;
  byId("disclosure").textContent = runtime.disclosure;
  byId("business").textContent = `${spec.business_display_name} — proposed workflow simulation`;
  const state = spec.states.find((item) => item.id === session.current_state);
  byId("state").textContent = JSON.stringify({
    state: session.current_state,
    terminal: state ? state.terminal : "unknown",
    components: state ? state.components : [],
    synthetic_persona: session.persona_id,
  }, null, 2);
  byId("receipts").textContent = session.receipts.length
    ? JSON.stringify(session.receipts, null, 2)
    : "No mock action yet.";
}

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Runtime request failed");
  return payload;
}

async function start() {
  const capability = location.hash.startsWith("#capability=")
    ? decodeURIComponent(location.hash.slice(12))
    : "";
  history.replaceState(null, "", "/");
  if (!capability) throw new Error("A one-time authenticated capability is required.");
  const payload = await post("/runtime/v1/capabilities/exchange", {
    capability,
    persona_id: "facility_manager_avery",
    seed: "local-preview-1",
  });
  runtime = payload.runtime;
  sessionToken = payload.session_token;
  render();
}

for (const event of allowedEvents) {
  const option = document.createElement("option");
  option.value = event;
  option.textContent = event;
  byId("event").append(option);
}

byId("advance").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const payload = await post("/runtime/v1/events", {
      session_token: sessionToken,
      event: byId("event").value,
      value: byId("value").value || null,
      duration_ms: null,
    });
    runtime = payload.runtime;
    render();
  } catch (error) {
    byId("error").textContent = error instanceof Error ? error.message : String(error);
  }
});

start().catch((error) => {
  byId("error").textContent = error instanceof Error ? error.message : String(error);
});
