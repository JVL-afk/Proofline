"""READ-ONLY consolidated Slots 07-24 evidence extraction. Runs in-VPC via a
transient research-worker task-def revision (entryPoint override). SELECT only;
contact-shaped substrings redacted defensively.
"""
import json
import re

from opintel_research_local import get_research_worker_settings
from sqlalchemy import create_engine, inspect, text

CONTACT = re.compile(
    r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"
    r"|(?<!\d)(?:\+?1[ .\-]?)?\(?\d{3}\)?[ .\-]\d{3}[ .\-]\d{4}(?!\d)"
)


def rd(v):
    return CONTACT.sub("[redacted-contact]", v) if isinstance(v, str) else v


APPROVED_HOSTS = {
    7: "polarprosac.com", 8: "www.villasplumbing.com", 10: "viconequip.com",
    11: "www.callsinclair.com", 12: "villageplumbing.com", 14: "citysupplygroup.com",
    16: "meritsvc.com", 18: "eliteaustinac.com", 19: "www.aplusac.com",
    20: "www.emergencyac.org", 21: "www.comfort-air.com", 22: "www.ramseyandco.com",
}
HOST2SLOT = {h: s for s, h in APPROVED_HOSTS.items()}

url = get_research_worker_settings().resolved_database_url()
eng = create_engine(url, future=True)
out = {"slots": {}, "batch": {}}

with eng.connect() as c:
    insp = inspect(c)
    tabs = set(insp.get_table_names())

    def q(sql, **p):
        return c.execute(text(sql), p).mappings().all()

    biz = q(
        "SELECT id, name, canonical_url, permitted_host, created_at "
        "FROM research_businesses WHERE created_at > '2026-08-30T13:00:00+00:00'"
    )
    for b in biz:
        host = b["permitted_host"]
        slot = HOST2SLOT.get(host)
        if slot is None:
            continue
        s = {"slot": slot, "business_identity": b["name"], "exact_hostname": host,
             "business_id": b["id"], "canonical_url": b["canonical_url"],
             "business_created_at": str(b["created_at"])}
        runs = q(
            "SELECT id, status, pages_attempted, pages_succeeded, bytes_stored, "
            "last_error_code, last_error_message, coverage_record_sha256, created_at, completed_at "
            "FROM research_runs WHERE business_id=:b ORDER BY created_at DESC", b=b["id"])
        s["research_run_count"] = len(runs)
        run = runs[0] if runs else None
        if run:
            rid = run["id"]
            s["m1"] = {
                "research_run_id": rid, "status": run["status"],
                "pages_attempted": run["pages_attempted"], "pages_succeeded": run["pages_succeeded"],
                "bytes_stored": run["bytes_stored"],
                "last_error_code": run["last_error_code"],
                "last_error_message": rd(run["last_error_message"]),
                "coverage_record_sha256": run["coverage_record_sha256"],
                "started_at": str(run["created_at"]), "completed_at": str(run["completed_at"]),
            }
            fc = q("SELECT fact_class, count(*) n FROM research_evidence WHERE research_run_id=:r "
                   "GROUP BY fact_class ORDER BY n DESC", r=rid)
            s["m1"]["evidence_total"] = sum(x["n"] for x in fc)
            s["m1"]["fact_class_histogram"] = {x["fact_class"]: x["n"] for x in fc}
            pp = q("SELECT page_purpose, count(*) n FROM research_pages WHERE research_run_id=:r "
                   "GROUP BY page_purpose ORDER BY n DESC", r=rid)
            s["m1"]["page_purpose_histogram"] = {x["page_purpose"]: x["n"] for x in pp}
            snaps = q("SELECT count(*) n, COALESCE(sum(removed_email_count),0) re, "
                      "COALESCE(sum(removed_phone_count),0) rp, "
                      "COALESCE(sum(removed_structured_contact_blocks),0) rs, "
                      "COALESCE(sum(content_length),0) cl "
                      "FROM page_snapshots WHERE research_run_id=:r", r=rid)[0]
            s["minimization"] = {
                "durable_minimized_snapshots": snaps["n"],
                "removed_email": snaps["re"], "removed_phone": snaps["rp"],
                "removed_structured_contact_blocks": snaps["rs"],
                "minimized_content_bytes": snaps["cl"],
            }
            if "research_capture_quarantines" in tabs:
                qs = q("SELECT source_uri, quarantine_reasons_json, minimizer_version "
                        "FROM research_capture_quarantines WHERE research_run_id=:r", r=rid)
                s["minimization"]["quarantines"] = [
                    {"source_uri": rd(x["source_uri"]),
                     "reasons": json.loads(x["quarantine_reasons_json"]),
                     "minimizer_version": x["minimizer_version"]} for x in qs]
            else:
                s["minimization"]["quarantines"] = []
            if run["coverage_record_sha256"] and "research_coverage_record" in tabs:
                cov = q("SELECT payload_json FROM research_coverage_record WHERE research_run_id=:r",
                        r=rid)
                if cov:
                    p = json.loads(cov[0]["payload_json"])
                    s["m1"]["coverage"] = {k: p.get(k) for k in (
                        "stop_reason", "useful_page_fetches", "total_http_requests",
                        "discovery_fetches", "pages_attempted", "pages_succeeded",
                        "distinct_categories_captured", "high_priority_categories_unattempted",
                        "crawl_protocol_version", "total_bytes")}

        # opportunity chain
        ar = q("SELECT id, status, hypothesis_id, created_at FROM opportunity_analysis_runs "
               "WHERE business_id=:b ORDER BY created_at DESC", b=b["id"])
        if ar:
            a = ar[0]
            s["m2"] = {"analysis_run_id": a["id"], "analysis_status": a["status"]}
            hyp = q("SELECT id, logical_id, statement, status, economic_run_id, score_snapshot_id, "
                    "company_fact_ids_json FROM opportunity_hypothesis_revisions "
                    "WHERE business_id=:b ORDER BY created_at DESC", b=b["id"])
            if hyp:
                h = hyp[0]
                s["m2"]["hypothesis_id"] = h["id"]
                s["m2"]["hypothesis_logical_id"] = h["logical_id"]
                s["m2"]["hypothesis_status"] = h["status"]
                s["m2"]["statement"] = rd(h["statement"])
                eco = q("SELECT status, result_label, monthly_value, annualized_value, currency, "
                        "formula_version FROM opportunity_economic_runs WHERE id=:e",
                        e=h["economic_run_id"])
                if eco:
                    s["m2"]["economics"] = {
                        "status": eco[0]["status"], "result_label": rd(eco[0]["result_label"]),
                        "monthly_value": eco[0]["monthly_value"],
                        "annualized_value": eco[0]["annualized_value"],
                        "currency": eco[0]["currency"], "formula_version": eco[0]["formula_version"]}
                sc = q("SELECT review_priority_band, config_version, review_rank_hint_json "
                       "FROM opportunity_score_snapshots WHERE id=:s", s=h["score_snapshot_id"])
                if sc:
                    s["m2"]["internal_review_priority_band"] = sc[0]["review_priority_band"]
                    s["m2"]["factor_config_version"] = sc[0]["config_version"]
                    s["m2"]["review_rank_hint"] = (
                        json.loads(sc[0]["review_rank_hint_json"])
                        if sc[0]["review_rank_hint_json"] else None)
                cf = q("SELECT category, phrase, fact_class, page_purpose, selector_version "
                       "FROM opportunity_company_facts "
                       "WHERE hypothesis_id IN (:h, :lg) ORDER BY category",
                       h=h["id"], lg=h["logical_id"])
                s["m2"]["company_facts"] = [
                    {"category": x["category"], "phrase": rd(x["phrase"]),
                     "fact_class": x["fact_class"], "page_purpose": x["page_purpose"],
                     "selector_version": x["selector_version"]} for x in cf]

        au = q("SELECT id, audit_id, revision, state, validity, revision_hash, findings_json "
               "FROM audit_revisions WHERE business_id=:b ORDER BY created_at DESC", b=b["id"])
        if au:
            a = au[0]
            findings = json.loads(a["findings_json"]) if a["findings_json"] else []
            s["m3"] = {"audit_revision_id": a["id"], "audit_id": a["audit_id"],
                       "revision_hash": a["revision_hash"],
                       "state": a["state"], "validity": a["validity"],
                       "finding_kinds": sorted({f.get("kind") for f in findings}),
                       "finding_count": len(findings),
                       "coverage_finding_text": rd(next(
                           (f.get("text") for f in findings if f.get("kind") == "crawl_coverage"),
                           None))}
            de = q("SELECT id, demo_id, revision, state, validity FROM demo_revisions "
                   "WHERE audit_id IN (:a, :ar) ORDER BY revision DESC",
                   a=a["audit_id"], ar=a["id"])
            if de:
                d0 = de[0]
                s["m4"] = {"demo_revision_id": d0["id"], "demo_id": d0["demo_id"],
                           "revision": d0["revision"], "state": d0["state"],
                           "validity": d0["validity"]}
                orv = q("SELECT id, package_id, revision, state, validity, data_json FROM "
                        "outreach_package_revisions WHERE demo_id=:d ORDER BY revision DESC",
                        d=d0["demo_id"])
                if orv:
                    o = orv[0]
                    data = json.loads(o["data_json"])
                    pers = data.get("personalization") or {}
                    s["m5"] = {
                        "outreach_revision_id": o["id"], "package_id": o["package_id"],
                        "revision": o["revision"], "state": o["state"], "validity": o["validity"],
                        "personalization": {
                            "company_specific_segment_count":
                                pers.get("company_specific_segment_count"),
                            "distinct_fact_classes": pers.get("distinct_fact_classes"),
                            "passes_gate": pers.get("passes_gate")},
                        "unresolved_slot_kinds": sorted(data.get("unresolved_slot_kinds", [])),
                        "qc_finding_codes": sorted({
                            f.get("code") for f in data.get("qc_findings", [])
                            if isinstance(f, dict)}),
                        "projection_modes": sorted({
                            p.get("mode") for p in data.get("projections", [])
                            if isinstance(p, dict)}),
                        "data_json_keys": sorted(data.keys()),
                    }

        out["slots"][str(slot)] = s

    # batch-wide research_businesses table totals (sanity)
    out["batch"]["research_businesses_total"] = q(
        "SELECT count(*) n FROM research_businesses")[0]["n"]
    out["batch"]["research_runs_total"] = q("SELECT count(*) n FROM research_runs")[0]["n"]

print("SLOTS0724_BEGIN")
print(json.dumps(out, default=str, sort_keys=True))
print("SLOTS0724_END")
