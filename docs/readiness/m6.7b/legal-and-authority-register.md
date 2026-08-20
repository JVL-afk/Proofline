# M6.7B Current-Law and Source-Authority Register

**Reviewed:** 2026-08-20
**Jurisdictional scope:** United States; Texas Phase 1
**Status:** Research record, not legal advice or legal approval

Only primary government/standards sources are used below. The proposition column states why the
source matters to architecture; it does not assert that a law applies or that a particular use is
lawful. Applicability, defenses, exceptions, contracts, and risk acceptance require qualified
counsel where indicated.

| Authority | URL | Jurisdiction | Policy proposition supported | Required project treatment |
|---|---|---|---|---|
| Texas Business & Commerce Code Chapter 541 | https://statutes.capitol.texas.gov/Docs/BC/pdf/BC.541.pdf | Texas | Consumer-data law defines scope, duties, rights, security, assessments, and exclusions; public availability is defined, not a blanket reuse permission | Counsel determines controller/applicability, public-information treatment, notices/requests, assessments, and exemptions before live data |
| Texas Attorney General TDPSA overview | https://www.texasattorneygeneral.gov/consumer-protection/file-consumer-complaint/consumer-privacy-rights/texas-data-privacy-and-security-act | Texas | Official overview states effective date, data minimization, security, rights, and that publicly available information is excluded from the Act's personal-data definition | Treat as guidance, not legal advice; retain conservative incidental-data controls regardless of possible exclusion |
| Texas Business & Commerce Code Chapter 521 | https://statutes.capitol.texas.gov/docs/bc/pdf/bc.521.pdf | Texas | Businesses must protect covered sensitive personal information and destroy covered records not retained | Counsel determines applicability; security/deletion design must not rely on public-source status alone |
| Texas Comptroller Franchise Tax Account Status | https://comptroller.texas.gov/taxes/franchise/account-status/ | Texas | Official public search advertises a public API for entity status | Candidate discovery source only after exact API documentation/terms/field review |
| TDLR Air Conditioning and Refrigeration Contractors | https://www.tdlr.texas.gov/acr/ | Texas | Official regulator provides an ACR license search and explains licensing relevance | Potential vertical-verification source; person-license content keeps it disabled pending field/privacy/terms review |
| RFC 9309 Robots Exclusion Protocol | https://www.rfc-editor.org/rfc/rfc9309.html | Internet standard | Defines crawler product token, allow/disallow matching, access-result behavior, caching, and states robots is not access control | Implement compliant parsing plus stricter fail-closed project rules; never treat robots as legal authorization |
| 18 U.S.C. § 1030 | https://uscode.house.gov/view.xhtml?preview=true&req=%28title%3A18+section%3A1030+edition%3Aprelim%29 | United States | Federal statute addresses access without authorization/exceeding authorization in specified circumstances | No authentication, access-control bypass, credential/session use, or adversarial access; counsel reviews edge cases |
| 17 U.S.C. § 106 | https://uscode.house.gov/view.xhtml?edition=prelim&req=granuleid%3AUSC-prelim-title17-section106 | United States | Copyright owners hold exclusive reproduction and derivative/distribution rights subject to statutory limitations | Source fidelity, excerpts, storage, and reuse need source-specific/counsel review; public display does not erase copyright |
| NIST Privacy Framework | https://www.nist.gov/privacy-framework/privacy-framework | U.S. voluntary framework | Provides lifecycle-oriented privacy-risk governance; it is not binding law | Use as architectural risk-management guidance, not legal authority |
| NIST SP 800-88 Rev. 2 | https://csrc.nist.gov/pubs/sp/800/88/r2/final | U.S. technical guidance | Current media-sanitization guidance ties sanitization/disposal to information sensitivity | Deletion/backup implementation should produce verifiable sanitization evidence appropriate to storage technology |
| NIST SP 800-92 | https://csrc.nist.gov/pubs/sp/800/92/final | U.S. technical guidance | Provides enterprise log-management guidance | Define restricted log content, access, lifecycle, and incident use before production |
| FTC CAN-SPAM guidance | https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business | United States | Commercial-email rules apply to B2B as well as bulk email | Later outreach/delivery gate only; public-research approval grants no email authority |

## Questions requiring qualified legal/privacy review

1. Does the operator/controller fall within TDPSA scope, and how do statutory public-information,
   small-business, processor, and other exemptions apply to this exact processing?
2. Are privacy notices, consumer-request procedures, contracts, or a data-protection assessment
   required before the proposed restricted incidental-data processing?
3. Do Texas Chapter 521, the Texas Data Broker Act, other state laws, or laws outside Texas apply to
   incidental individuals, source operators, or the chosen environment?
4. What retention values and legal-hold rules are justified for each data class?
5. Are exact discovery APIs/directories and each website's terms compatible with the proposed
   access, capture, extraction, storage, and audit purpose?
6. What copyright/fair-use/licensing analysis applies to immutable page copies and excerpts?
7. Are the proposed crawler identity, robots handling, rate limits, and access controls adequate for
   the exact sites and access method?
8. What notices, contracts, incident response, breach notification, or cross-border transfer rules
   apply to the selected cloud/provider/region?

## Research versus outreach

M6.7B covers only discovery and public research. It authorizes no contact discovery, recipient
resolution, message preparation change, email, call, form submission, booking, or other external
communication. CAN-SPAM and all M6/M6.5 delivery gates remain separate even if research is later
authorized.
