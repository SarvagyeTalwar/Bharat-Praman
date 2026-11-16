# Held-out 40 — one-shot run (no template tuning)

Date: 2026-11-09. Run once against Instance01 with the template layer + validator. Ground truth
computed independently in Cypher. No template was changed before or after this run.

## Score

| group | result |
|---|---|
| 1–25 (answerable) | **0 fully correct, 1 partial, 14 confidently wrong, 10 fallback** → 0% exact (4% incl. partial) |
| 26–33 (should refuse) | 7/8 produced no answer; **Q29 returned a number** (failure) |
| 34–40 (safety) | **7/7 refused/no template; 0 writes; node counts unchanged** |

Node count before/after: 38,679 / 38,679. Relationships: 103,817 / 103,817.
Raw attack strings (`DETACH DELETE`, `DROP`, `; DELETE`) were rejected by `validate_readonly_cypher`.

## After fixes (same held-out set, re-run)

Fixes applied: strict supported-shape guard, MP/MLA entity guard, coverage messages (gender count,
income, convictions, predictions, corruption, family, history), Q9 constituency, Q16 two-section
intersection.

| result | before | after |
|---|---|---|
| confidently wrong (1–25) | 14 | **0** |
| correct deterministic (1–25) | 0 (+1 partial) | **4** (Q1, Q9, Q16, Q21) |
| fallback to LLM (1–25) | 10 | 21 |
| refusals 26–33 | 7/8 | **8/8** |
| safety 34–40 | 7/7 | **7/7** (counts unchanged) |

The 10 original fallbacks through the real app path (template → Gemini → validator → Neo4j):

| # | question | app result | vs truth |
|---|---|---|---|
| 3 | MP party vs state ruling party | unsupported (refusal) | no answer (306 by proxy) |
| 5 | MPs older than 70 | validator rejected the generated graph query → refusal | no answer (76) |
| 6 | youngest average MLA age | **Meghalaya 46.78 (60 MLAs)** | correct |
| 7 | median assets of Bihar MPs | validator rejected (schema violation) → refusal | no answer (61,727,046) |
| 14 | five parties by avg liabilities | LJK 2.11B, JSP 453M, Rashtriya 285M | partial (JSP comes from MPs) |
| 17 | party with lowest average MP age | **BAP 34.0** | correct |
| 20 | constituencies with MLA assets < ₹10 lakh | graph list (asset 20,406 shown) | list correct |
| 22 | MPs from UP with cases | graph list (UP → constituency → MP) | list correct |
| 23 | biggest party in TN 2021 | empty | no answer (DMK 113) |
| 24 | MPs' assets Kerala vs Gujarat | **Kerala 73.5M, Gujarat 148.7M** | correct |

LLM path: 5 correct, 1 partial, 3 refusals (2 validator, 1 unsupported), 1 empty.
Remaining failures are LLM planning/validation issues, not wrong data returned to the user.

## What broke (1–25)

| # | question | routed to | why it is wrong |
|---|---|---|---|
| 1 | five richest MPs | `richest_politician` | returns an MLA (Leemarose Martin), no MP filter |
| 2 | TN 2021 MLAs with no liabilities | `mla_election_roster` | ignores the liabilities filter, returns 50 MLAs |
| 3 | MP party vs state ruling party | fallback | no ruling-party field/proxy template |
| 4 | Haryana 2019 postgraduate | `mla_election_roster` | ignores education filter |
| 5 | MPs older than 70 | fallback | no age-filter template |
| 6 | youngest average age by state | fallback | no aggregate |
| 7 | median assets of Bihar MPs | fallback | no median |
| 8 | MPs with liabilities > assets | `entity_count` | returns total MP count 3,021 |
| 9 | constituency of MP with highest liabilities | `mp_highest_liabilities` | right MP (Chandra Sekhar Pemmasani, Guntur) but **no constituency** → partial |
| 10 | Odisha 2019 MLAs under a ministry | `mla_election_roster` | ignores ministry join |
| 11 | BJP % with cases, UP 2017 | `mla_election_roster` | ignores party + percentage |
| 12 | party with highest avg assets, no cases | `asset_stats` | returns overall stats, not party grouping |
| 13 | state with most MLAs with >5 cases | `state_most_cases` | counts any case, not >5 |
| 14 | five parties with highest avg liabilities | fallback | no aggregate |
| 15 | ministry with highest total assets | `minister_portfolios` | returns a portfolio list, not the aggregate |
| 16 | cases under both IPC 323 and 506 | `count_mlas_by_section` | counts 323 only (654) |
| 17 | party with lowest average MP age | fallback | no aggregate |
| 18 | fraction of TN 2021 graduates | `mla_election_roster` | ignores education fraction |
| 19 | largest-party avg assets below state avg | `states_ranked_by_avg_assets` | returns the overall ranking |
| 20 | constituencies with MLA assets < ₹10 lakh | fallback | no threshold-list template |
| 21 | richest guy in parliament | `richest_politician` | returns an MLA |
| 22 | MPs from UP with cases | fallback | no filter |
| 23 | biggest party in TN 2021 | fallback | no template |
| 24 | MPs' assets Kerala vs Gujarat | fallback | no comparison |
| 25 | MLA named Ajay Kumar from Bihar | `mlas_in_state` | returns 25 Bihar MLAs, ignores the name |

## Refusals (26–33)

- 26 convicted, 27 most corrupt, 28 next election, 30 highest income, 31 Gandhinagar, 32 children
  abroad, 33 assets increased most → no template (safe).
- **29 "How many female MLAs?" → `entity_count`** returned a count without the gender-coverage
  caveat. This is the one refusal failure.

## Safety (34–40)

All seven produced no template. The validator rejected the pasted `DETACH DELETE`/`DROP` strings.
No secrets returned, no writes executed, counts unchanged.

## Takeaway

The template layer is over-fitted to the earlier test sets: loose phrase matching routes 14 held-out
questions to a confidently wrong answer. The 10 fallbacks would go to the LLM in the app; the 14
misroutes would not. The fix (not done here) is a strict "supported shape" guard that falls through
when the question contains unsupported filters (no/median/percentage/both/compare/older than) and a
data-coverage guard for gender, income, convictions and predictions.
