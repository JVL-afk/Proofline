"use strict";

const apiBase = "http://127.0.0.1:8000";
let businessId = null;
let researchRunId = null;
let opportunityRunId = null;
let hypothesisId = null;
let hypothesisRevisionId = null;

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
    if (["succeeded", "partial"].includes(run.status)) {
      byId("start-opportunity").disabled = false;
    }
  } catch (error) {
    showError(error);
  }
});

byId("start-opportunity").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const run = await request(`/api/v1/businesses/${businessId}/opportunity-analysis-runs`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ research_run_id: researchRunId }),
    });
    opportunityRunId = run.id;
    byId("opportunity").textContent = JSON.stringify(run, null, 2);
    byId("refresh-opportunity").disabled = false;
  } catch (error) {
    showError(error);
  }
});

byId("refresh-opportunity").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const result = await request(`/api/v1/opportunity-analysis-runs/${opportunityRunId}/result`);
    byId("opportunity").textContent = JSON.stringify(result, null, 2);
    if (result.hypothesis) {
      hypothesisId = result.hypothesis.logical_id;
      hypothesisRevisionId = result.hypothesis.id;
      byId("recalculate").disabled = false;
      byId("accept-opportunity").disabled = result.hypothesis.status !== "ready_for_review";
      byId("reject-opportunity").disabled = false;
    }
  } catch (error) {
    showError(error);
  }
});

byId("recalculate").addEventListener("click", async () => {
  const proposed = (key, element) => ({
    key,
    value_state: "proposed",
    decimal_value: byId(element).value,
    source_kind: "USER_PROPOSED",
    provenance: "local diagnostic scenario",
  });
  try {
    const result = await request(`/api/v1/opportunities/${hypothesisId}/recalculate`, {
      method: "POST",
      body: JSON.stringify({
        expected_hypothesis_revision_id: hypothesisRevisionId,
        assumptions: [
          proposed("monthly_inbound_leads", "monthly-leads"),
          proposed("affected_share", "affected-share"),
          proposed("conversion_lift", "conversion-lift"),
          proposed("average_customer_value", "customer-value"),
        ],
      }),
    });
    byId("opportunity").textContent = JSON.stringify(result, null, 2);
    hypothesisRevisionId = result.hypothesis.id;
    byId("accept-opportunity").disabled = result.hypothesis.status !== "ready_for_review";
  } catch (error) {
    showError(error);
  }
});

async function review(decision) {
  try {
    const result = await request(`/api/v1/opportunities/${hypothesisId}/review-decisions`, {
      method: "POST",
      body: JSON.stringify({
        expected_hypothesis_revision_id: hypothesisRevisionId,
        decision,
        reason: `Local diagnostic ${decision} decision.`,
      }),
    });
    byId("opportunity").textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    showError(error);
  }
}

byId("accept-opportunity").addEventListener("click", () => review("accept"));
byId("reject-opportunity").addEventListener("click", () => review("reject"));
