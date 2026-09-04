# M4 builder-brief — A-Plus vs Elite personalization proof (2026-09-04)

Owner authorization 2026-09-04 "M4 BUILDER-BRIEF V3.1 CLEANUP + ELITE
PERSONALIZATION PROOF", Part II. Both briefs are produced by the **same
generalized compiler** (`demo.builder_brief@3.1`, `opintel_communication.builder_story`)
from each business's **frozen existing evidence only** — no re-research, no web,
no new evidence.

* A-Plus source: `tests/m68_fixtures.aplus_envelope()` — envelope sha256
  `c5a6307f4427d450359946b87d64cecd43f090ed28946c90bd175eaa2b0b380e`
* Elite source: `tests/m68_fixtures.elite_envelope()` — envelope sha256
  `2eca7a18a88c657ec52428f25c5e78224cbda553ef84fe92fed308f430e91d55`

## 1. Side-by-side semantic comparison

| axis | A-Plus | Elite |
|---|---|---|
| **eligible public evidence** | intake surface (`"When to Schedule AC Replacement"`), commercial context (`"Commercial Air Conditioning Repairs"`), **response commitment** (`"…flat-rate pricing, fast response times, and technicians registered with the State of Texas"`, self-claim, not quotable), service-area (generic) | intake surface (`"Need to schedule a service call?"`), commercial context (`"Commercial HVAC Services"`), **24-hour service availability** (`"About Our 24-Hour Service"`), service-area (`"Just a Sample of Our Service Areas"`) |
| **primary demo anchor** | `response commitment` | `service availability` |
| **opportunity headline** | *"One way structured intake could support the **response experience** your public pages already describe"* | *"One way structured intake could complement the **service availability** your public pages already describe"* |
| **40–50 word opportunity summary** | *"Your public pages emphasize commercial HVAC repair and feature a published **response-time message**. We built a short simulation showing how a structured intake flow could prepare a commercial request for human follow-up. We don't know your current internal process, systems, staffing, or response performance."* | *"Your public pages emphasize commercial HVAC repair and feature a published **availability message**. We built a short simulation showing how a structured intake flow could prepare a commercial request for human follow-up. We don't know your current internal process, systems, staffing, or response performance."* |
| **scenario framing (per-anchor)** | *"a commercial request, **organized and summarized** so a person can pick it up"* | *"a service request **that could come in at any time**, organized so a person can pick it up"* |
| **"Why we built this" evidence bullets** | 3 — response-time message · `"Commercial Air Conditioning Repairs"` · `"When to Schedule AC Replacement"` | 4 — service-availability message · `"Commercial HVAC Services"` · `"Need to schedule a service call?"` · `"Just a Sample of Our Service Areas"` |
| **Screen 2 fields / synthetic values** | Service need · Facility · Service location · Urgency · Equipment · Preferred follow-up — synthetic values (`Repair request` / `Example service location` / …) | **identical** (shared mechanics, section 14) |
| **Screen 3 result story** | Request → Structured context → Example human review → Next workflow preparation; stage 2 line: *"…turns the form answers into a commercial request, organized and summarized so a person can pick it up."* | **same 4 stages**; stage 2 line: *"…turns the form answers into a service request that could come in at any time, organized so a person can pick it up."* |
| **grouped customer outcomes** | Lead record · Human follow-up · Scheduling context (six mock actions preserved) | **identical** (shared mechanics) |
| **fictional handoff** | Morgan — Intake coordinator | Casey — Intake coordinator (deterministic per business name) |
| **closing bridge** | *"Imagine this fitted to your actual intake process rather than this hypothetical one."* | **identical** |
| **why this is specific to the business** | A-Plus is the only one of the two whose public pages carry a **published response-time / response-positioning** claim; the whole opportunity is framed around *supporting that response experience* with organized, summarized intake. | Elite is the only one of the two whose public pages carry a **24-hour service-availability** signal and an explicit **"schedule a service call"** intake path; the opportunity is framed around a *service request that could arrive at any time*, organized for a person — **availability is context, never upgraded into a claim that Elite answers / acknowledges / dispatches / responds 24/7** (enforced by the compiler's availability→response check). |

## 2. Blind test

> If the business names were hidden, would a reviewer still be able to tell these
> demos arose from **materially different evidence**?

**Yes.** With the names, hostnames and the fictional handoff name removed, a
reviewer comparing the two briefs still sees:

1. a **different primary anchor** — "response experience" vs "service
   availability" — stated in the Screen-1 headline;
2. a **different published signal quoted** in the opportunity summary
   ("response-time message" vs "availability message");
3. a **different set of quoted public phrases** in "Why we built this"
   (`"When to Schedule AC Replacement"` vs `"Need to schedule a service call?"`,
   plus Elite's extra service-area quote);
4. a **different scenario premise** carried into the result story ("organized and
   summarized" vs "a service request that could come in at any time").

These four differences are all **downstream of the two envelopes' different
eligible facts** — not visual novelty. A reviewer would correctly conclude the
A-Plus brief was built from response-positioning evidence and the Elite brief
from 24-hour-availability + service-call-scheduling evidence.

### Honest scoping

The distinctiveness lives entirely in the **opportunity layer** (anchor,
headline, summary, evidence list, scenario framing, result stage-2 line). The
**simulation mechanics** — Screen 2's fields and synthetic values, the four
result stages' structure, the three grouped outcomes, the handoff role, the
closing bridge — are **byte-identical** between the two briefs. That is
deliberate and authorized (section 14: "same underlying intake engine with
different reason/story/context" is acceptable; fabricating a different internal
workflow to look personalized is not). A reviewer shown **only Screen 2** could
not tell the two briefs apart — by design.

## 3. Verdict

**`PERSONALIZATION_PROOF_PASSED`**

Different evidence produces a meaningfully different **opportunity story**:
different anchor, different quoted public signal, different scenario premise, all
traceable to the two businesses' different frozen public facts. Shared intake
mechanics are shared on purpose, within the section-14 allowance.

If the owner later wants divergence to reach into Screen 2 / Screen 3 as well
(e.g. an anchor-aware `simulation_intake_title` such as "Simulate a service-call
request" for Elite), that is a small, evidence-grounded extension — but it is not
required for this proof and carries a manufactured-difference risk the owner
explicitly flagged, so it was **not** done here.

## 4. Confirmation — authoritative M4 unchanged

- `git status packages/demo-core/` is empty — no `opintel_demo` file touched.
- Elite's brief is a projection of the V2 `BuilderExperience` → V1 `BuilderBrief`,
  whose full `_assert_within_authority` M4 check runs first and unchanged
  (`underlying_brief_sha256 91808fc5…` for Elite).
- Elite: all six mock actions preserved verbatim; every explicit UNKNOWN carried
  in the audit layer; the safety exception and the availability→response
  prohibition enforced by the same checks as A-Plus.

## 5. Artifacts

| artifact | path |
|---|---|
| A-Plus V3.1 machine-readable | `docs/readiness/demo-builder-brief/m4-aplus-builder-brief-v3-2026-09-03.json` |
| A-Plus V3.1 paste-ready `.md` | `docs/readiness/demo-builder-brief/m4-aplus-builder-brief-v3-2026-09-03.md` |
| **Elite V3.1 machine-readable** | `docs/readiness/demo-builder-brief/m4-elite-builder-brief-v3.1-2026-09-04.json` |
| **Elite V3.1 paste-ready `.md`** | `docs/readiness/demo-builder-brief/m4-elite-builder-brief-v3.1-2026-09-04.md` |
| this comparison | `docs/readiness/demo-builder-brief/m4-aplus-vs-elite-personalization-2026-09-04.md` |
