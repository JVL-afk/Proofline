"use strict";

const apiBase = "http://127.0.0.1:8000";
let businessId = null;
let researchRunId = null;

const byId = (id) => document.getElementById(id);

function token() {
  return sessionStorage.getItem("local-token") || "";
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${token()}`);
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${apiBase}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({ detail: "invalid API response" }));
  if (!response.ok) {
    throw new Error(`${response.status}: ${payload.detail || "request failed"}`);
  }
  return payload;
}

function showError(error) {
  byId("error").textContent = error instanceof Error ? error.message : String(error);
}

byId("authenticate").addEventListener("click", async () => {
  byId("error").textContent = "";
  sessionStorage.setItem("local-token", byId("token").value);
  try {
    const identity = await request("/api/v1/session");
    byId("identity").textContent = `${identity.subject} — workspace ${identity.workspace_id}`;
  } catch (error) {
    sessionStorage.removeItem("local-token");
    showError(error);
  }
});

byId("create-business").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const business = await request("/api/v1/businesses", {
      method: "POST",
      body: JSON.stringify({
        name: byId("business-name").value,
        public_url: byId("public-url").value,
      }),
    });
    businessId = business.id;
    byId("business").textContent = `${business.name} — ${business.canonical_url}`;
    byId("start-research").disabled = false;
  } catch (error) {
    showError(error);
  }
});

byId("start-research").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const run = await request(`/api/v1/businesses/${businessId}/research-runs`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        policy: { max_pages: 5, max_depth: 1, per_domain_delay_seconds: 0.25 },
      }),
    });
    researchRunId = run.id;
    byId("refresh-research").disabled = false;
    byId("research-run").textContent = JSON.stringify(run, null, 2);
  } catch (error) {
    showError(error);
  }
});

byId("refresh-research").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const run = await request(`/api/v1/research-runs/${researchRunId}`);
    byId("research-run").textContent = JSON.stringify(run, null, 2);
    const pages = await request(`/api/v1/research-runs/${researchRunId}/pages`);
    byId("pages").textContent = JSON.stringify(pages, null, 2);
    const evidence = await request(`/api/v1/research-runs/${researchRunId}/evidence`);
    byId("research-evidence").textContent = JSON.stringify(evidence, null, 2);
  } catch (error) {
    showError(error);
  }
});
