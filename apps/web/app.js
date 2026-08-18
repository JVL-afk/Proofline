"use strict";

const apiBase = "http://127.0.0.1:8000";
let businessId = null;
let researchRunId = null;
let opportunityRunId = null;
let hypothesisId = null;
let hypothesisRevisionId = null;
let auditOperationId = null;
let auditRevision = null;
let demoOperationId = null;
let demoRevision = null;
let outreachOperationId = null;
let outreachRevision = null;
let personId = null;
let contactPointId = null;
let senderIdentityId = null;
let sendManifestId = null;
let sendManifestHash = null;
let sendPreviewHash = null;
let sendAuthorizationId = null;
let deliveryAttemptId = null;

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
      byId("start-audit").disabled = !["ready_for_review", "accepted"].includes(
        result.hypothesis.status,
      );
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
    byId("start-audit").disabled = !["ready_for_review", "accepted"].includes(
      result.hypothesis.status,
    );
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

byId("start-audit").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const result = await request(`/api/v1/opportunities/${hypothesisId}/audit-revisions`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ expected_hypothesis_revision_id: hypothesisRevisionId }),
    });
    auditOperationId = result.operation.id;
    byId("audit").textContent = JSON.stringify(result, null, 2);
    byId("refresh-audit").disabled = false;
  } catch (error) {
    showError(error);
  }
});

byId("refresh-audit").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const operation = await request(`/api/v1/audit-operations/${auditOperationId}`);
    if (!operation.operation.audit_revision_id) {
      byId("audit").textContent = JSON.stringify(operation, null, 2);
      return;
    }
    const result = await request(
      `/api/v1/audit-revisions/${operation.operation.audit_revision_id}`,
    );
    auditRevision = result.revision;
    byId("audit").textContent = JSON.stringify(result, null, 2);
    const reviewable = auditRevision.state === "review_required";
    byId("approve-audit").disabled = !reviewable || auditRevision.kind !== "full";
    byId("reject-audit").disabled = !reviewable;
    byId("start-demo").disabled = auditRevision.state !== "approved";
  } catch (error) {
    showError(error);
  }
});

async function reviewAudit(decision) {
  try {
    const result = await request(
      `/api/v1/audit-revisions/${auditRevision.id}/review-decisions`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_revision_hash: auditRevision.revision_hash,
          expected_manifest_hash: auditRevision.manifest.checksum,
          decision,
          reason: `Local diagnostic audit ${decision} decision.`,
          acknowledged_qc_codes: [],
        }),
      },
    );
    auditRevision = result.revision;
    byId("audit").textContent = JSON.stringify(result, null, 2);
    byId("approve-audit").disabled = true;
    byId("reject-audit").disabled = true;
    byId("start-demo").disabled = auditRevision.state !== "approved";
  } catch (error) {
    showError(error);
  }
}

byId("approve-audit").addEventListener("click", () => reviewAudit("approve"));
byId("reject-audit").addEventListener("click", () => reviewAudit("reject"));

byId("start-demo").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const result = await request(`/api/v1/audit-revisions/${auditRevision.id}/demo-revisions`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ expected_audit_revision_hash: auditRevision.revision_hash }),
    });
    demoOperationId = result.operation.id;
    byId("demo").textContent = JSON.stringify(result, null, 2);
    byId("refresh-demo").disabled = false;
  } catch (error) {
    showError(error);
  }
});

byId("refresh-demo").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const operation = await request(`/api/v1/demo-operations/${demoOperationId}`);
    if (!operation.operation.demo_revision_id) {
      byId("demo").textContent = JSON.stringify(operation, null, 2);
      return;
    }
    const result = await request(`/api/v1/demo-revisions/${operation.operation.demo_revision_id}`);
    demoRevision = result.revision;
    byId("demo").textContent = JSON.stringify(result, null, 2);
    const reviewable = demoRevision.state === "review_required";
    byId("approve-demo").disabled = !reviewable;
    byId("reject-demo").disabled = !reviewable;
    byId("launch-demo").disabled = demoRevision.state !== "approved";
    byId("start-outreach").disabled = demoRevision.state !== "approved";
  } catch (error) {
    showError(error);
  }
});

async function reviewDemo(decision) {
  try {
    const result = await request(`/api/v1/demo-revisions/${demoRevision.id}/review-decisions`, {
      method: "POST",
      body: JSON.stringify({
        expected_revision_hash: demoRevision.revision_hash,
        expected_manifest_hash: demoRevision.manifest.checksum,
        expected_specification_hash: demoRevision.specification_hash,
        decision,
        reason: `Local deterministic demo ${decision} decision.`,
      }),
    });
    demoRevision = result.revision;
    byId("demo").textContent = JSON.stringify(result, null, 2);
    byId("approve-demo").disabled = true;
    byId("reject-demo").disabled = true;
    byId("launch-demo").disabled = demoRevision.state !== "approved";
    byId("start-outreach").disabled = demoRevision.state !== "approved";
  } catch (error) {
    showError(error);
  }
}

byId("approve-demo").addEventListener("click", () => reviewDemo("approve"));
byId("reject-demo").addEventListener("click", () => reviewDemo("reject"));

byId("launch-demo").addEventListener("click", async () => {
  try {
    const issued = await request(`/api/v1/demo-revisions/${demoRevision.id}/session-issuances`, {
      method: "POST",
      body: JSON.stringify({ expected_revision_hash: demoRevision.revision_hash }),
    });
    const target = `${issued.runtime_origin}/#capability=${encodeURIComponent(issued.capability)}`;
    window.open(target, "_blank", "noopener,noreferrer");
  } catch (error) {
    showError(error);
  }
});

byId("start-outreach").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const result = await request(
      `/api/v1/demo-revisions/${demoRevision.id}/outreach-package-operations`,
      {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ expected_demo_revision_hash: demoRevision.revision_hash }),
      },
    );
    outreachOperationId = result.operation.id;
    byId("outreach").textContent = JSON.stringify(result, null, 2);
    byId("refresh-outreach").disabled = false;
  } catch (error) {
    showError(error);
  }
});

byId("refresh-outreach").addEventListener("click", async () => {
  byId("error").textContent = "";
  try {
    const operation = await request(
      `/api/v1/outreach-package-operations/${outreachOperationId}`,
    );
    if (!operation.operation.outreach_revision_id) {
      byId("outreach").textContent = JSON.stringify(operation, null, 2);
      return;
    }
    const result = await request(
      `/api/v1/outreach-package-revisions/${operation.operation.outreach_revision_id}`,
    );
    outreachRevision = result.revision;
    byId("outreach").textContent = JSON.stringify(result, null, 2);
    const reviewable = outreachRevision.state === "ready_for_review";
    byId("approve-outreach").disabled = !reviewable;
    byId("reject-outreach").disabled = !reviewable;
  } catch (error) {
    showError(error);
  }
});

async function reviewOutreach(decision) {
  try {
    const result = await request(
      `/api/v1/outreach-package-revisions/${outreachRevision.id}/review-decisions`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_revision_hash: outreachRevision.revision_hash,
          expected_manifest_hash: outreachRevision.manifest.checksum,
          expected_content_hash: outreachRevision.content_hash,
          decision,
          reason: `Local M5 content-only ${decision} decision.`,
        }),
      },
    );
    outreachRevision = result.revision;
    byId("outreach").textContent = JSON.stringify(result, null, 2);
    byId("approve-outreach").disabled = true;
    byId("reject-outreach").disabled = true;
    byId("identify-contact").disabled = outreachRevision.state !== "content_approved";
  } catch (error) {
    showError(error);
  }
}

byId("approve-outreach").addEventListener("click", () =>
  reviewOutreach("approve_content"),
);
byId("reject-outreach").addEventListener("click", () => reviewOutreach("reject"));

byId("identify-contact").addEventListener("click", async () => {
  try {
    const person = await request(
      `/api/v1/outreach-package-revisions/${outreachRevision.id}/person-identities`,
      {
        method: "POST",
        body: JSON.stringify({
          full_name: byId("fixture-person").value,
          functional_role: "service_operations_lead",
          source_uri: "fixture://m6/ui/person",
          source_locator: "ui.person[0]",
        }),
      },
    );
    personId = person.record.id;
    const contact = await request(`/api/v1/person-identities/${personId}/contact-points`, {
      method: "POST",
      body: JSON.stringify({
        value: byId("fixture-contact").value,
        acquisition_origin: "observed",
        source_uri: "fixture://m6/ui/contact",
        source_locator: "ui.contact[0]",
      }),
    });
    contactPointId = contact.record.id;
    byId("contact-control").textContent = JSON.stringify({ person, contact }, null, 2);
    byId("verify-contact").disabled = false;
    byId("refresh-timeline").disabled = false;
  } catch (error) {
    showError(error);
  }
});

byId("verify-contact").addEventListener("click", async () => {
  try {
    const result = await request(
      `/api/v1/contact-points/${contactPointId}/verification-operations`,
      { method: "POST" },
    );
    byId("contact-control").textContent = JSON.stringify(result, null, 2);
    byId("evaluate-contact").disabled = false;
  } catch (error) {
    showError(error);
  }
});

byId("evaluate-contact").addEventListener("click", async () => {
  try {
    const result = await request(
      `/api/v1/contact-points/${contactPointId}/eligibility-evaluations`,
      { method: "POST", body: JSON.stringify({ purpose: "b2b_first_contact" }) },
    );
    byId("contact-control").textContent = JSON.stringify(result, null, 2);
    byId("create-sender").disabled = result.record.state !== "eligible";
  } catch (error) {
    showError(error);
  }
});

byId("create-sender").addEventListener("click", async () => {
  try {
    const result = await request("/api/v1/sender-identities", {
      method: "POST",
      body: JSON.stringify({
        display_name: "Alex Fixture",
        mailbox: "sender@fixture.invalid",
        signature: "Alex Fixture, Fixture Outreach",
        postal_disclosure: "123 Fixture Way, Austin, TX 78701",
        opt_out_instruction: "Reply opt out to stop fixture messages.",
      }),
    });
    senderIdentityId = result.record.id;
    byId("contact-control").textContent = JSON.stringify(result, null, 2);
    byId("prepare-send").disabled = false;
  } catch (error) {
    showError(error);
  }
});

byId("prepare-send").addEventListener("click", async () => {
  try {
    const result = await request(
      `/api/v1/outreach-package-revisions/${outreachRevision.id}/send-readiness`,
      {
        method: "POST",
        body: JSON.stringify({
          contact_point_id: contactPointId,
          sender_identity_id: senderIdentityId,
          artifact_kind: "first_contact_email",
        }),
      },
    );
    sendManifestId = result.manifest.id;
    sendManifestHash = result.manifest_hash;
    sendPreviewHash = result.manifest.preview_hash;
    byId("contact-control").textContent = JSON.stringify(result, null, 2);
    byId("authorize-send").disabled = !result.readiness.passed;
  } catch (error) {
    showError(error);
  }
});

byId("authorize-send").addEventListener("click", async () => {
  try {
    const result = await request(`/api/v1/send-manifests/${sendManifestId}/authorizations`, {
      method: "POST",
      body: JSON.stringify({
        expected_manifest_hash: sendManifestHash,
        expected_preview_hash: sendPreviewHash,
        reason: "One exact synthetic fixture message approved in the diagnostic UI.",
      }),
    });
    sendAuthorizationId = result.record.id;
    byId("contact-control").textContent = JSON.stringify(result, null, 2);
    byId("submit-send").disabled = false;
  } catch (error) {
    showError(error);
  }
});

byId("submit-send").addEventListener("click", async () => {
  try {
    const result = await request(
      `/api/v1/send-authorizations/${sendAuthorizationId}/delivery-attempts`,
      { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() } },
    );
    deliveryAttemptId = result.record.id;
    byId("contact-control").textContent = JSON.stringify(result, null, 2);
    byId("submit-send").disabled = true;
    byId("record-receipt").disabled = result.record.state !== "provider_accepted";
  } catch (error) {
    showError(error);
  }
});

byId("record-receipt").addEventListener("click", async () => {
  try {
    const result = await request(
      `/api/v1/delivery-attempts/${deliveryAttemptId}/fixture-events`,
      {
        method: "POST",
        body: JSON.stringify({
          event_id: crypto.randomUUID(),
          event_type: "delivered",
          body: "",
          signature: "fixture-signature-v1",
        }),
      },
    );
    byId("contact-control").textContent = JSON.stringify(result, null, 2);
    byId("record-receipt").disabled = true;
  } catch (error) {
    showError(error);
  }
});

byId("refresh-timeline").addEventListener("click", async () => {
  try {
    const result = await request(`/api/v1/businesses/${businessId}/interaction-timeline`);
    byId("interaction-timeline").textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    showError(error);
  }
});
