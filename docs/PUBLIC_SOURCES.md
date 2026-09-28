# Public source register

This register contains only public pages opened during the current verification.
No collector task is authorized by this file until the source's robots and terms
are reviewed again at collection time.

| Source | Start URL | Public need it may show | robots.txt | Terms | Opened |
|---|---|---|---|---|---|
| TED Search API — candidate, NOT CLEARED for ForgeOS ingestion | https://api.ted.europa.eu/v3/notices/search | Published procurement notices; official documentation says analysis/reuse is supported | `https://api.ted.europa.eu/robots.txt` returned `404`; the separate `https://ted.europa.eu/robots.txt` disallows dynamic browser search query URLs but allows `/simap/xml-bulk-download`. No API robots prohibition was found; this does not settle field-level permission | Official API docs state published notices are available anonymously for analysis/reuse and describe commercial buyer/vendor services, but no machine-readable field schema, numerical rate cap, or blanket license for the selected notice fields was established. One bounded API request returned HTTP 400 for unsupported `fields` values. No results were returned or persisted | 2026-09-28 |
| Nepal Public Procurement Monitoring Office / Bolpatra | https://bolpatra.gov.np/egp/ | Official e-GP procurement notices and tenders | `https://bolpatra.gov.np/robots.txt` and `/egp/robots.txt` returned maintenance-page HTML, not directives. PPMO's separate `https://www.ppmo.gov.np/robots.txt` states `Crawl-delay: 10` for that host only | No applicable automation/API/reuse terms or license found; procurement collection is NOT CLEARED | Opened 2026-09-25; rechecked 2026-09-28 |
| Kathmandu Post | https://kathmandupost.com/ | Public notices or tender reporting | `403`; not cleared | The landing page returned `403`; terms were not cleared | 2026-09-25 |
| Nepal Rastra Bank | https://www.nrb.org.np/ | Public notices | `200` text; `User-agent: *` disallows `/wp-admin/` only | `https://www.nrb.org.np/disclaimer/` returned `404`. No terms page granting collection was found | 2026-09-25 |
| The Rising Nepal | https://risingnepaldaily.com/ | Public notices in news pages | `200` text; `User-agent: *` allows `/` and disallows login, admin, api, and search. Named AI crawlers are disallowed | Privacy policy at `https://risingnepaldaily.com/privacy-policy` describes the site's own visitor tracking. It does not grant collection | 2026-09-25 |
| Gorkhapatra Online | https://gorkhapatraonline.com/ | Public notices in news pages | `200` text; `User-agent: *` disallows admin, login, password, api, and search. Named AI crawlers are disallowed | No terms URL granting collection was opened | 2026-09-25 |
| Department of Industry | https://www.doind.gov.np/ | Public industry notices | `200` text; `User-agent: *` with an empty `Disallow:` | The landing page returned `200`. No terms URL granting collection was found | 2026-09-25 |
| Nepal Law Commission | https://www.lawcommission.gov.np/ | Published laws and notices | `200` text; `User-agent: *` and `Crawl-delay: 10`, with no `Disallow` | The landing page returned `200`. No terms, copyright, or disclaimer link was found | 2026-09-25 |
| Public Service Commission | https://www.psc.gov.np/ | Public vacancy notices | `200` text; `User-agent: *` with an empty `Disallow:` | The landing page returned `200`. No terms, copyright, or disclaimer link was found | 2026-09-25 |
| U.S. International Trade Administration, Nepal distribution guide | https://www.trade.gov/country-commercial-guides/nepal-distribution-sales-channels | Public description of Nepal distribution channels | `200` text; `User-agent: *` does not disallow this path. Disallowed paths are admin, search, user, and core | `https://www.trade.gov/endorsement-disclaimer` is an endorsement disclaimer. It does not grant collection | 2026-09-25 |
| GovInfo, Federal Register notice on Nepal cultural-property import restrictions | https://www.govinfo.gov/content/pkg/FR-2026-08-12/html/2026-16432.htm | A public final rule restricting import of archaeological and ethnological material from Nepal | `https://www.govinfo.gov/robots.txt` returned `200` text. `User-agent: *` does not disallow `/content/`. Disallowed paths include `/search/` and `/app/search/*` | `https://www.govinfo.gov/about/policies` states that 17 U.S.C. § 105 places United States Government works in the public domain and that public documents can generally be reprinted without legal restriction. Third-party copyrighted material inside a document is not covered | 2026-09-25 |
| Crossref REST API `/works` | https://api.crossref.org/works | Search publicly registered scholarly bibliographic metadata for research leads across topics and geographies | `https://api.crossref.org/robots.txt` returned `404`; integration uses only Crossref's documented API, not general site crawling | Crossref REST API docs at `https://www.crossref.org/documentation/retrieve-metadata/rest-api/` state no signup is required and almost all metadata may be reused; some abstracts may be copyrighted. The adapter requests only DOI, title, publisher, type, publication dates, container title, citation count, and authors; abstracts/full text are excluded. Public rate limits are conservatively restricted to one request per minute | 2026-09-27 |
| OpenAlex Works REST API | https://api.openalex.org/works | Keyword and semantic discovery of scholarly work metadata and reconstructed abstracts as literature observations; not direct evidence of local customer pain, demand, or intervention effectiveness | `https://api.openalex.org/robots.txt` returned `200`; `User-agent: *` allows `/`. Runtime policy rechecks this endpoint before a Works API request | Official OpenAlex API reference at `https://help.openalex.org/api/` states keyless basic use is available and “all data is CC0”; API documentation supports `search`, `search.semantic`, and `per_page`. Clearance allows only `/works` over HTTPS, 1–100 keyword results or 1–50 semantic results; semantic query text is capped at 2,000 characters. Persistent one-second pacing applies to both modes. Planner selects keyword mode for explicit exact phrases, author/paper lookups, or identifiers and semantic mode for broad conceptual requests; task and Evidence provenance retain the original question, exact derived query, mode, geographic/population qualifications, and unresolved dimensions. `abstract_inverted_index` is reconstructed from JSON. The adapter stores neither `pdf_url`/`oa_url` nor raw publisher landing pages and never requests external PDFs or publisher HTML. A DOI/OpenAlex ID, title, year, citation count, bounded author/institution-country and concept summaries, access booleans, and abstract are retained. Signal identity is a SHA-256 hash of the canonical OpenAlex Work ID and is enforced atomically for concurrent writes. Affiliation countries are not study geography; publication year is not study period. Retrieval relevance and citations remain discovery metadata, not empirical support, local applicability, opportunity evidence, or market demand. Empty result sets produce a distinct metadata-only retrieval Signal and task observation, no Evidence, and no claim effect | 2026-09-27 |
| Semantic Scholar Academic Graph API — candidate, NOT cleared | https://api.semanticscholar.org/graph/v1/paper/search | Candidate scholarly abstract search for substantive research | `https://api.semanticscholar.org/robots.txt` returned `404`; API-only access was inspected, not general website crawling | Official API license at `https://www.semanticscholar.org/product/api/license` says S2 Data is separately governed by accompanying data licenses and underlying third-party content may have its own license; it also requires attribution to “Semantic Scholar”. The requested Graph API response fields do not identify an applicable per-paper/abstract license. The endpoint probe on 2026-09-27 returned HTTP 429; no abstract was retained. The API product page recommends an API key; `SEMANTIC_SCHOLAR_API_KEY` was not configured. No abstract collection or persistence is approved until compatible product use and per-item content-license compliance are established, and access can proceed without violating provider rate limits | 2026-09-27 |
| World Bank Indicators API v2 — bounded country indicator endpoints | https://api.worldbank.org/v2 | Read-only country-year indicators and separate indicator/source metadata for macro statistical observations | `https://api.worldbank.org/robots.txt` returned `404`; integration uses only the documented JSON API and exact `/v2/indicator/{id}` and `/v2/country/{country}/indicator/{id}` path forms over HTTPS | The World Bank Data Catalog licensing page says CC BY 4.0 is the default for World Bank-produced open datasets, but many datasets have other licenses, including externally specified and custom licenses. WDI metadata identifies source organizations; those are captured, not treated as proof of exclusive ownership or an indicator-specific license. Attribution is retained. Macro data cannot establish customer pain, product demand, local market demand, or willingness to pay. Persistent rate gate: at least 1 second between API calls | 2026-09-27 |
| GDELT DOC API v2 — bounded article metadata | https://api.gdeltproject.org/api/v2/doc/doc | Observe matching article title, URL, domain, publication date, language, and source country; metadata describes coverage and is not verification of the article's claims | `https://api.gdeltproject.org/robots.txt` returned `404`; collector uses only the documented API endpoint and fixed `artlist` mode over HTTPS | Official GDELT DOC API documentation at `https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/` documents JSON output, article metadata, and volume timelines. The GDELT data overview is `https://gdeltproject.org/data.html`. Clearance attribution tag: `GDELT Open Data (Unlimited reuse with attribution to https://www.gdeltproject.org/)`; this does not grant rights to publisher article bodies or images, which are never fetched or stored. The persistent source gate enforces the provider's observed five-second pacing guidance; HTTP 429 receives bounded exponential backoff, then defers the task without consuming an attempt. Article metadata may satisfy media coverage and recent-event observations. It may satisfy only a narrow GDELT-indexed article count over a bounded window when the result set is uncapped; a capped list cannot measure reporting velocity. No GDELT metadata may establish customer pain, market demand, willingness to pay, or financial viability | 2026-09-27 |
| ILOSTAT SDMX REST API — candidate, NOT cleared | https://sdmx.ilo.org/rest/v1 | Candidate public aggregate country-level labor statistics; restricted constituent microdata explicitly excluded | Exact SDMX robots policy was not established; metadata reads only, with no observation collection | ILO's official policy states datasets published/made available on or after 2023-05-03 are CC BY 4.0, excluding restricted constituent microdata. `DF_EMP_TEMP_SEX_AGE_NB` metadata exposes a `LAST_UPDATE` annotation but no dataset publication date or explicit license tag; no data was persisted. Dataset-specific eligibility and API terms remain unverified; no collector clearance | 2026-09-27 |
| Nepal Office of Company Registrar (OCR), Public Data Portal — candidate, NOT CLEARED | https://ocr.gov.np/ links to https://company.ocr.gov.np/ and `/company-register` | Public-company verification/search. OCR's portal advertises free public access to CAMIS-updated registration data and search by PAN, company name, or registration number. The company table exposes English/Nepali legal name, registration number, masked PAN, type, status, address, registration date, and expiry date | `https://ocr.gov.np/robots.txt` returned `User-agent: *` and `Crawl-delay: 10` for the OCR host. `https://company.ocr.gov.np/robots.txt` returned the SPA HTML shell, not a robots policy for the company-data subdomain | The portal says common public functions need no login and the company-search page presents a mathematical challenge before search. No portal terms, privacy notice, API specification, reuse license, prospecting permission, automated access permission, rate limit, or permitted commercial purpose was found. `/terms` and `/privacy` returned the app shell without policy text. The UI exposed `/api/public/v1/company-register` as a resource; it is not documented as a supported public API. A default page load in this review triggered its first-page listing; no search was submitted, no detail opened, no company row copied into Forge, and no candidate/prospect was created. This incidental UI request is not source clearance or a discovery exercise. Personal/contact/shareholder/beneficial-owner fields and their availability/permission were not inspected. Do not automate or reuse this source for prospecting without OCR's explicit written authorization covering the exact interface, data fields, use, retention, and rate | 2026-09-28 |

## Operating rule

The register is descriptive, not permission to collect. A research task may use
only a row whose robots and terms are both explicitly cleared. No signal or
domain record is created from these pages by this register alone.

The web collector allowlists only the exact GovInfo Federal Register URL
above, only on its recorded review date (UTC). Before fetching that page, it
re-reads robots.txt and the policies page, checks that this path remains allowed
and the reviewed permission plus copyright caveat remain present, and fails
closed on changes or network errors. Redirects must remain at the exact
allowlisted URL. A database-backed source gate enforces the minimum interval
across API and worker instances. The manual review expires at the UTC date
change; review robots.txt and terms again, then update the code and this date
before another day's collection. Every other `web` task is failed before a
network request. Reddit, GitHub, RSS, and arXiv collectors are also blocked
inside their collector implementations until separately cleared. Crossref is a
separate documented metadata API integration, limited to the fixed `/works`
endpoint, public bibliographic fields, a 60-second persistent minimum interval,
and the review window recorded in the runtime registry. Returned metadata is a
discovery lead, not the contents of the underlying paper or proof of a market
claim.

Semantic Scholar is a reviewed candidate only, not a runtime clearance. Its
official API license (linked above) requires compliance with the licenses
accompanying S2 Data and any underlying Third Party Content, and requires
attribution. The requested search response fields do not include a per-record
content license, so an abstract cannot currently be verified as eligible for
storage in Forge Evidence or use in a commercial research loop. The one live
endpoint probe returned HTTP 429; do not retry until access is appropriately
authenticated or the provider permits retry. Do not add Semantic Scholar to
the runtime registry, persist abstracts, or mark problem-incidence/alternatives
requirements answerable until these conditions are reviewed and evidenced. A
local one-request-per-second throttle cannot override provider responses or
data-license requirements.

World Bank Indicators API v2 is a bounded, reviewed capability for annual
country-level numeric observations only. The adapter makes HTTPS GET requests
to `/v2/country/{country_code}/indicator/{indicator_id}` and a separate
`/v2/indicator/{indicator_id}` metadata path, bounded to a maximum 21-year
window and exact ISO country/indicator syntax. It stores only the declared
observation fields plus the indicator metadata required for attribution;
unrelated API response fields are discarded. The indicator metadata call is
necessary because the observation payload's `source` may be null while the
metadata contains `source`, `sourceOrganization`, and `sourceNote`. Provenance
retains this attribution and flags when third-party source organizations are
listed, without inferring exclusive ownership or an indicator-specific license.
Collection fails closed if the current Data Catalog license language cannot be
rechecked. Persistent rate reservation enforces a one-second minimum between
both API calls.

World Bank evidence is limited to macro requirements
(`macro_demographics`, `population_baseline`, and `economic_indicator`) and
must match the requested country, indicator, and year scope. It cannot satisfy
customer pain, product demand, problem incidence, alternatives/prices, or
buyer willingness-to-pay requirements. The current indicator API does not
report an item-specific license; provenance records the World Bank Data
Catalog's dataset-level default and its exception for other licenses rather
than asserting each indicator is individually CC BY 4.0.

Reviewed live examples:

- `https://api.worldbank.org/v2/country/NPL/indicator/SP.POP.TOTL`
- `https://api.worldbank.org/v2/indicator/SP.POP.TOTL`
- API v2 overview: `https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation`
- API call structure: `https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures`
- Data license: `https://datacatalog.worldbank.org/public-licenses`
- API robots response: `https://api.worldbank.org/robots.txt` (404; the integration uses the documented API endpoints)

Runtime approvals live in `backend/app/services/source_clearance_registry.py`.
Each entry binds one exact HTTPS target to its source ID, country/category
scope, allowed need, evidence references, robots URL, terms URL, required
permission/copyright language, redirect allowlist, policy-host allowlist,
review dates, and minimum request interval. Registry validation rejects
duplicate IDs/URLs, non-HTTPS or unapproved policy links, broad redirects,
missing evidence, unsupported collectors, and invalid review windows. The
runtime registry currently has five entries: the expired GovInfo page (still
blocked), time-limited Crossref, World Bank Indicators, GDELT, and OpenAlex
entries. None supports `authorized_prospect_discovery`. The Semantic Scholar,
ILOSTAT, OCR, and Bolpatra rows above remain research notes, not collection
permissions. A source becomes usable only after source-specific review is
documented here, a typed runtime entry binds its exact target/purpose/fields
and review window, its adapter validates the exact `CollectionAuthorization`,
and any live robots/terms checks and persistent rate reservation pass. Registry
tests ensure runtime URLs and documentation references remain connected.

### OCR Public Data Portal — discovery clearance decision (2026-09-28)

The official OCR site links the CAMIS portal as a public service. The portal's
landing page describes free access to updated company registration data and
states that general public functions do not require login. Its company-search
page presents a mathematical challenge and describes lookup by PAN, name, or
registration number. The visible company table has legal names, registration
number, masked PAN, entity type/status, business address, and registration/
expiry dates. The landing page's advertised database total and the register
page's result total differed during inspection; neither count is treated as a
validated registry total.

This establishes that human-facing lookup and some company-level attributes
are publicly presented; it does **not** establish permission for bots, bulk
enumeration, API use, commercial prospecting, or retention/reuse. The portal
does not expose a written terms/privacy or reuse policy in its UI. Its
`/terms` and `/privacy` routes served the application shell without policy
text; its subdomain `robots.txt` also served application HTML rather than
robots directives. The OCR parent site's 10-second robots crawl delay is
specific to `ocr.gov.np` and cannot be assumed to authorize automated requests
to `company.ocr.gov.np`. The public UI's mathematical challenge is an
interactive control and must not be bypassed. Only masked PAN was visible in
the table reviewed; unmasked identifiers, detail-page fields, contact people,
shareholders, and beneficial-owner data were not inspected and are not cleared.

While opening `/company-register` to inspect the user-facing form, the
application automatically loaded its default first-page listing from the
undocumented `/api/public/v1/company-register` resource. The UI rendered ten
rows and reported 181,992 results; the home page had separately advertised
111,290 registered companies. No search criteria were submitted, no entity
was selected or copied to Forge, no detail view was opened, and no prospect
was recorded. This incidental page-load request was not authorized prospect
discovery and must not be repeated by a collector.

**Decision: NOT CLEARED.** Before any request beyond normal manual public use,
obtain OCR's written, applicable authorization or published terms that
explicitly permit automated access and reuse for business/prospect discovery,
identify a documented machine interface and allowed request shape, confirm
permitted fields (excluding personal/contact/shareholder/beneficial-owner data
unless separately authorized), scope, rate, retention, attribution, privacy
basis, and review/expiry date. Then add the exact clearance plus a bounded
adapter and tests. Do not treat public display, a browser-visible endpoint, or
a successful HTTP response as authorization.

### PPMO / Bolpatra procurement source decision (2026-09-28)

The official Nepal Public Procurement Monitoring Office (PPMO) site is
`https://www.ppmo.gov.np/`; its homepage identifies the office and exposes an
e-GP help-desk reference. The official e-GP address listed for the system is
`https://bolpatra.gov.np/egp/`. At review time, the Bolpatra root, `/egp/`, and
both corresponding `robots.txt` URLs returned a system-maintenance page rather
than a search interface, machine-readable schema, or robots directives. The
PPMO host's separate `robots.txt` says `Crawl-delay: 10`; that rule does not
authorize access to the separate Bolpatra host.

No current API documentation, export contract, source terms/license, privacy
or retention rules, field list, rate limit, or permission for automated
retrieval and reuse for procurement-demand analysis was found. Whether the
portal allows read-only automation, historical notice reuse, or any
commercial-prospect identification is therefore **unknown**, not permitted.
Procurement demand analysis would establish only the public requirement in a
notice; it would not authorize contacting the procuring organization, imply
interest in ForgeOS, or establish customer status, willingness to pay, or a
sale. No notice search, record query, or procurement record retrieval was
performed; no organization or personal data was collected.

**Decision: NOT CLEARED.** Before machine access, obtain PPMO's current written
authorization or published terms that explicitly cover automated read-only
access and Opportunity-scoped procurement-demand analysis, a documented API
or export and query limits, permitted fields (excluding personal-contact
details unless separately authorized), geographic and historical scope,
privacy/retention and attribution rules, rate limits, and an effective/review
date. The source must be rechecked when the portal is operational. Public
notice visibility and the PPMO-host crawl delay are not a substitute for this
permission. Do not add a clearance, adapter, or live procurement query before
these conditions are evidenced.

### TED published procurement notices — candidate review, NOT CLEARED (2026-09-28)

The European Union Publications Office's official TED developer
[Search API documentation](https://docs.ted.europa.eu/api/latest/search.html)
describes `POST https://api.ted.europa.eu/v3/notices/search` for already
published procurement notices. It explicitly says published notices are
available anonymously for analysis and reuse, targets data reusers, and lists
commercial organizations integrating TED data into added-value services for
vendors and buyers. The general [TED API documentation](https://docs.ted.europa.eu/api/latest/index.html)
also confirms anonymous access for published-notice search/retrieval. This
establishes a strong, official purpose-compatible candidate; it does not
authorize bids, buyer contact, or treating a notice as ForgeOS-specific
interest, WTP, or customer evidence.

**Operational field contract not established.** The official API documentation
page names `POST /v3/notices/search` but does not provide a machine-readable
search request/response schema or supported selected-field catalog. To test
the documented interface, one request was attempted with a 3-day publication
date query, result limit 1, and only the intended notice ID/title/buyer/date/
deadline/country/CPV fields. TED returned HTTP 400 stating that one or more
`fields` values were unsupported and listing accepted values. The adapter
therefore received no notices; no retry was made, no records were returned,
and no source data was persisted. The API's live Swagger UI currently exposes
the general TED Apps API spec but not a retrievable schema for this Search
operation.

The API host's `/robots.txt` returned 404. TED's separate
`https://ted.europa.eu/en/robots.txt` disallows dynamic browser search query
URLs, but does not govern the distinct API host. TED's Search API documentation
does not state a numeric request quota, notice-field-specific license/rights,
or retention terms. The HTTP 400 also prevents verifying the exact allowed
minimal fields. No source clearance or adapter is registered; the registry
continues to fail closed for TED. The attempted request reserved the local
persistent source rate gate; no further TED request should be made until the
one-hour interval has elapsed and the exact supported, permitted field schema
has been established.

**Precise unlock:** obtain the Search API's current machine-readable schema or
written TED confirmation mapping the public notice ID, subject/title,
contracting authority, publication/deadline, CPV, and country fields to valid
request names; confirm those fields are covered by its reuse permission and
privacy/retention conditions; and obtain the source's numeric rate policy or
written permission for a conservative client-side interval. Then add only
those fields to the registry, implement the exact documented request, and
perform one bounded, rate-compliant read-only search. Until then, public
availability and general-purpose reuse language are not enough to clear the
unverified field contract.

## 2026-09-27 — Third-party license hardening and ILOSTAT review

World Bank records whose indicator metadata lists source organizations are
stored with `license_status: "unconfirmed_third_party"` and
`license_compatibility_verified: false` unless compatible item-specific reuse
terms have been explicitly verified. The research planner will not use those
records to satisfy even macro baseline requirements. It retains the traceable
Evidence as a lead, with an explicit rejection reason; the World Bank
dataset-level default is not treated as proof of third-party rights.

ILOSTAT was inspected but not registered. The official ILO
[rights-and-permissions policy](https://www.ilo.org/rights-and-permissions)
says datasets and referential metadata published or made available on/after
2023-05-03 are CC BY 4.0, except restricted microdata from constituents and
partners; pre-date datasets do not automatically carry that license. Live
metadata for
[`DF_EMP_TEMP_SEX_AGE_NB`](https://sdmx.ilo.org/rest/v1/dataflow/ILO/DF_EMP_TEMP_SEX_AGE_NB/latest?references=children)
returned HTTP 200 and described "Employment by sex and age". Its flow/structure
metadata showed a `LAST_UPDATE` annotation but no dataset publication date or
explicit CC BY 4.0 tag. That update timestamp is not treated as proof of the
license eligibility condition. Exact SDMX robots and endpoint terms were not
established, and no labor observations were retrieved or persisted. ILOSTAT
remains blocked pending dataset-specific publication/license evidence and
permission review.
