# Public source register

This register contains only public pages opened during the current verification.
No collector task is authorized by this file until the source's robots and terms
are reviewed again at collection time.

| Source | Start URL | Public need it may show | robots.txt | Terms | Opened |
|---|---|---|---|---|---|
| Nepal Public Procurement Monitoring Office / Bolpatra | https://bolpatra.gov.np/ | Public procurement notices and tenders | `200` HTML maintenance page, not a robots file. `https://bolpatra.gov.np/egp/robots.txt` was the same maintenance page | The public landing page returned `200`; no separate terms URL was established, so collection remains unapproved | 2026-09-25 |
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
| Semantic Scholar Academic Graph API — candidate, NOT cleared | https://api.semanticscholar.org/graph/v1/paper/search | Candidate scholarly abstract search for substantive research | `https://api.semanticscholar.org/robots.txt` returned `404`; API-only access was inspected, not general website crawling | Official API license at `https://www.semanticscholar.org/product/api/license` says S2 Data is separately governed by accompanying data licenses and underlying third-party content may have its own license; it also requires attribution to “Semantic Scholar”. The requested Graph API response fields do not identify an applicable per-paper/abstract license. The endpoint probe on 2026-09-27 returned HTTP 429; no abstract was retained. The API product page recommends an API key; `SEMANTIC_SCHOLAR_API_KEY` was not configured. No abstract collection or persistence is approved until compatible product use and per-item content-license compliance are established, and access can proceed without violating provider rate limits | 2026-09-27 |
| World Bank Indicators API v2 — bounded country indicator endpoints | https://api.worldbank.org/v2 | Read-only country-year indicators and separate indicator/source metadata for macro statistical observations | `https://api.worldbank.org/robots.txt` returned `404`; integration uses only the documented JSON API and exact `/v2/indicator/{id}` and `/v2/country/{country}/indicator/{id}` path forms over HTTPS | The World Bank Data Catalog licensing page says CC BY 4.0 is the default for World Bank-produced open datasets, but many datasets have other licenses, including externally specified and custom licenses. WDI metadata identifies source organizations; those are captured, not treated as proof of exclusive ownership or an indicator-specific license. Attribution is retained. Macro data cannot establish customer pain, product demand, local market demand, or willingness to pay. Persistent rate gate: at least 1 second between API calls | 2026-09-27 |

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
runtime registry currently has three entries: the expired GovInfo page (still
blocked), the time-limited Crossref API row, and the time-limited World Bank
Indicators API v2 row. The Semantic Scholar row above remains a research note,
not a collection permission. When a source is reviewed, update its evidence
row and add a typed runtime entry; registry tests ensure runtime URLs and
documentation references remain connected.
