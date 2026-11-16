# Demo accuracy notes

## What the graph can answer

Text-to-Cypher uses the labels, properties, and relationship directions declared in `main.py`. It supports graph paths and aggregate results. The UI shows aggregate values in a table and renders entity relationships as a graph. The API rejects unknown labels, relationship types, and properties, requires a bounded result, and runs the query through a Neo4j read session.

The graph has no `MP` label, spouse/wife relationship, or dependable current-office flag. Those questions are reported as unsupported instead of guessing. A `FACES` relationship means that a case is linked to a person; it is not evidence of guilt or conviction. Case status should be described as the status recorded in this graph.

## Data freshness

The metadata endpoint (`/api/metadata`) reports the latest source-document date and the share of nodes with a recorded date. The graph audit for the 2026-10-24 demo preparation found **18,632 nodes**, with a latest source-document date of **2024-06-09**. Only **131 nodes (0.7%)** have a source-document date. The Graph Explorer displays this metadata before a demo search. A source-document date is not proof that a record remains current.

Questions asking who currently holds office are marked unsupported until the data includes a verified as-of date or a maintained current-office field. If the demo needs current MPs, spouses, or official current office-holders, the graph must first be populated from appropriate maintained sources.

## Text-to-Cypher evaluation baseline

`research_questions_100.json` is the 100-question evaluation set. `research_query_results_100.json` records Gemini plans and Neo4j outcomes; `research_query_plans_checkpoint.json` preserves the raw plans from the batch run. On that run, 96 questions were schema-supported, 79 returned at least one row, and 17 returned no rows. Twelve Cypher strings needed syntax repair before execution. This measures query execution and result availability, not semantic accuracy; a reviewed set of expected answers is still needed for an accuracy score.

The local example catalog keeps graph and aggregate examples separate. The API loads it once per process and sends at most three relevant examples to Gemini. Re-run the evaluation after prompt/schema changes, inspect every failed or empty case, and manually verify a representative sample before presenting specific political claims.

## Phase 2 — cross-election and profile templates

Five deterministic, read-only templates were added in `cypher_templates.py`:

| template_id | answers |
|---|---|
| `mla_timeline` | party, declared assets, liabilities and criminal-case count by election for a named politician |
| `mla_case_change` | criminal-case count by election for a named politician |
| `mla_party_switchers` | MLAs whose recorded party differs across two or more elections (optional state filter) |
| `mla_election_roster` | MLAs recorded for a state and assembly-election year |
| `politician_profile` | latest recorded affidavit profile for a named politician |

All five are aggregate queries, take parameters, and pass `main.validate_readonly_cypher`. The validator
allow-list was extended with the `Affidavit` and `Election` labels, the `FILED`, `FOR_ELECTION`,
`CONTESTED` and `DISCLOSES` relationship types, and their properties (`election_id`, `election_year`,
`affidavit_id`, `person_key`, `person_entity_id`, `source_url`, `election_source`, `election_verified`,
`type`, `year`, `state`).

### Test questions and expected results (data snapshot 2026-11-09)

| # | question | template | expected result |
|---|---|---|---|
| 1 | How did Naveen Patnaik's assets change across elections? | mla_timeline | 5 rows: 2009 ₹7,89,97,076 · 2014 ₹12,06,37,433 · 2019 ₹63,87,31,815 (Bijepur) and ₹63,87,41,816 (Hinjili) · 2024 ₹71,07,78,364 |
| 2 | Show Naveen Patnaik's criminal case count across elections | mla_case_change | 5 rows, all 0 |
| 3 | Did Naveen Patnaik contest under different parties? | mla_timeline | 5 rows, all BJD |
| 4 | Which MLAs changed party? | mla_party_switchers | 25 rows; top: Braja Kishore Pradhan (BJD, Ind.) across 4 elections |
| 5 | Which MLAs switched parties in Odisha? | mla_party_switchers | 21 rows; e.g. Aswini Kumar Patra BJD/BJP (4 elections) |
| 6 | List MLAs from Tamil Nadu in 2011 | mla_election_roster | 50 rows (capped); first ALANDUR — S.ramachandran (DMDK) |
| 7 | Who is J Jayalalithaa? | politician_profile | TamilNadu2016, AIADMK, age 68, assets ₹1,13,73,38,586, liabilities ₹2,04,02,987, cases 4 |
| 8 | Tell me about D K Shivakumar | politician_profile | Karnataka2023, INC, age 60, assets ₹14,13,80,02,404, liabilities ₹5,03,07,30,087, cases 19 |
| 9 | How did Bhupinder Singh Hooda's liabilities change? | mla_timeline | 3 rows: 2014 ₹15,20,000 · 2019 ₹13,20,000 · 2024 ₹15,00,000 |
| 10 | List MLAs from Uttar Pradesh in 2017 | mla_election_roster | 50 rows (capped); first AGRA CANTT. — Girraj Singh Dharmesh (BJP) |

Notes:

- Roster questions return at most 50 rows because the read-only validator caps results at 50; narrow by
  state/year/party to see the rest.
- Values are as declared in the affidavit for that election. They are not inflation-adjusted and do not
  describe the person's current status.
- Criminal-case figures are counts declared in the affidavit; a `FACES` link is not evidence of guilt.
- Person timelines group by `person_key` (state + normalised name + shared seat); different people with
  the same name are not merged.

## Phase 2b — multi-hop templates (3–5 hops)

Added to answer questions that combine party, state, constituency, election and case data:

| template_id | hops | answers |
|---|---|---|
| `party_seats_in_state` | MLA → Affidavit → Election; party from affidavit | seats per party in a state (optional year) |
| `party_section_in_state` | MLA → Affidavit → Election; MLA → FACES → Case → UNDER → Section | party × IPC section × state |
| `party_sections` | MLA → MEMBER_OF → Party; MLA → FACES → Case → UNDER → Section | a party's most common IPC sections |
| `state_most_cases` | MLA → AssemblyConstituency → State; MLA → Affidavit → Election | states ranked by MLAs with declared cases |
| `mp_mla_counts_by_state` | MP → Constituency → State; MLA → AssemblyConstituency → State | MP and MLA counts for a state |
| `state_avg_assets` | MLA → AssemblyConstituency → State; MLA → Affidavit | average/max declared assets for a state |
| `states_ranked_by_avg_assets` | same, grouped by state | states ranked by average MLA assets |
| `largest_party_section` | MLA → Party; MLA → AssemblyConstituency → State; MLA → FACES → Case → UNDER → Section | largest party in a state + its top IPC sections |
| `constituency_winner` | MLA → AssemblyConstituency; MLA → Affidavit → Election | winner of a seat (optional year) |

### Multi-hop test questions and expected results (snapshot 2026-11-09)

| # | question | expected result |
|---|---|---|
| 1 | Which party has the most MLAs in Tamil Nadu 2021? | DMK 113, AIADMK 56 |
| 2 | Party-wise seat count in Uttar Pradesh 2017 | BJP 274, SP 46, BSP 17 |
| 3 | Which party's MLAs in Uttar Pradesh were charged under IPC 143? | BJP 31 MLAs / 39 cases; SP 14 / 22 |
| 4 | Which state has the most MLAs with criminal cases? | Uttar Pradesh 331, Tamil Nadu 307 |
| 5 | Which ministers have criminal cases? | 22 rows; first Bandi Sanjay Kumar (Home Affairs) 42 cases |
| 6 | How many MPs and MLAs does Uttar Pradesh have? | 80 MPs, 762 MLAs |
| 7 | Which IPC sections are most common among BJP MLAs? | 506 (424 cases), 147 (403) |
| 8 | What is the average asset of MLAs in Odisha? | 655 MLAs, avg ₹3,65,30,463, max ₹2,27,67,62,601 |
| 9 | In Odisha, which party has the most seats and what section are its MLAs charged under most? | BJD, 391 MLA records, section 506 (185 cases) |
| 10 | Who won Srirangam in 2011? | J Jayalalithaa, AIADMK, ₹51.41 Cr, 0 cases |

Run: 50 multi-hop questions → **50 answered by templates, 0 empty, 0 invalid/errors**, ~9 s total.
The 250-question general set → **212 answered by templates (84.8%)**, 38 fallback (14 unsupported
meta questions + money-list phrasings), 0 empty, 0 invalid.


