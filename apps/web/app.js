"use strict";

const apiBase = "http://127.0.0.1:8000";
let campaignId = null;
let operationId = null;

const byId = (id) => document.getElementById(id);

function token() {
  return sessionStorage.getItem("m0-token") || "";
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
  sessionStorage.setItem("m0-token", byId("token").value);
  try {
    const identity = await request("/api/v1/session");
    byId("identity").textContent = `${identity.subject} — workspace ${identity.workspace_id}`;
  } catch (error) {
    sessionStorage.removeItem("m0-token");
    showError(error);
  }
});

byId("create-campaign").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const campaign = await request("/api/v1/campaigns", {
      method: "POST",
      body: JSON.stringify({
        name: byId("campaign-name").value,
        fixture_uri: byId("fixture-uri").value,
      }),
    });
    campaignId = campaign.id;
    byId("campaign").textContent = `${campaign.name} — ${campaign.id}`;
    byId("start-operation").disabled = false;
  } catch (error) {
    showError(error);
  }
});

byId("start-operation").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const operation = await request(`/api/v1/campaigns/${campaignId}/operations`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    operationId = operation.id;
    byId("refresh-operation").disabled = false;
    byId("operation").textContent = JSON.stringify(operation, null, 2);
  } catch (error) {
    showError(error);
  }
});

byId("refresh-operation").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const operation = await request(`/api/v1/operations/${operationId}`);
    byId("operation").textContent = JSON.stringify(operation, null, 2);
    const evidence = await request(`/api/v1/operations/${operationId}/evidence`);
    byId("evidence").textContent = JSON.stringify(evidence, null, 2);
  } catch (error) {
    showError(error);
  }
});
