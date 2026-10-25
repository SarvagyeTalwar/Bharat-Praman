# Bharat Praman: Natural-Language Search Evaluation

**Evaluation date:** 24 October 2026  
**Question set:** 40 progressively difficult political-research questions  
**Purpose:** Estimate whether a normal user can ask questions in the current demo and receive useful, trustworthy answers.

## Executive summary

The demo is **promising for simple lookups and straightforward summaries, but not yet dependable enough for open-ended research**. On the 37 questions the system considered answerable, 26 returned a non-empty result in the expected display mode (70.3%). That headline score overstates quality: manual inspection found obvious missing logic in 8 of those 26 results. Eighteen of 37 supported questions (48.6%) were judged structurally plausible and complete by query-shape review. This is not a factual-accuracy score; there was no verified answer key for all questions.

For a normal user, a simple question such as “Which party is Rahul Gandhi connected to?” or “Show cases linked to Rahul Gandhi” is likely to work. A question that combines several filters, asks for a particular ranking, or expects multiple relationship branches in one graph is substantially less reliable. A user can receive a non-empty but incomplete result, which is more concerning than a visible error because it can look convincing.

**Demo recommendation:** suitable for guided demonstrations of supported, well-understood questions, provided the presenter explains the data date and checks results. Do not present it as a verified political-research assistant or use its output alone for reporting, publication, or claims about current officeholders.

## What was tested

The run tested 40 questions of increasing complexity across person profiles, parties, States, constituencies, assets, liabilities, family fields, portfolios, criminal-case records and Sections, aggregates, missing-data denominators, and multi-hop graph paths. The set included unsupported requests about MPs, spouses, and current office status to check whether the application would admit when its data cannot answer.

The app sent 37 requests to Gemini. Three unsupported requests were intercepted locally and did not call Gemini. The run recorded 73,129 Gemini tokens, completed in about six minutes, used no retries, and encountered no quota or rate-limit response. The dashboard figures provided for remaining quota were blank, so this run cannot establish the remaining free-tier balance. Google documents limits in requests per minute, input tokens per minute, and requests per day; the applicable values depend on the model and project and are shown in AI Studio. [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## Results

| Outcome | Count | What it means |
|---|---:|---|
| Supported questions with non-empty output in expected mode | 26/37 (70.3%) | Basic operational pass only; not proof the answer was complete or factually correct. |
| Structurally plausible, complete candidates after manual review | 18/37 (48.6%) | Query shape appeared to cover the request; still not checked against a gold factual answer. |
| Clear partial/incomplete non-empty results | 8 | Query returned something but omitted a requested branch, grouping, denominator, or statistic. |
| Wrong result mode | 2 | One aggregate/table request came back as a graph; one graph/table expectation was mismatched. |
| Empty result | 4 | Could mean no matching data, sparse fields, stale coverage, or a wrong generated query. It must not automatically be shown as “none exist.” |
| Validation or execution error | 5 | The system could not complete the request. |
| Unsupported requests correctly refused | 3/3 | MP, spouse, and verified-current-office requests were refused rather than invented. |

The 29/40 (72.5%) end-to-end figure counts the 18 plausible supported candidates, the three refusals, and eight other expected-type non-empty responses as if each were a pass. It is therefore an **operational response score**, not a quality or accuracy score. The more conservative 18/37 figure is the better signal for a normal user, and even that remains a manual structural estimate.

## What works best

- Direct person-to-party and person-to-case lookups (Q3–Q4).
- Several simple party/State comparisons and grouped counts (Q6–Q10, Q13, Q16–Q19, Q21, Q30, Q34).
- Straightforward graph paths such as party → MLA → case → Section (Q23) and party → MLA → constituency → State (Q24).
- Refusing unsupported data instead of fabricating an answer (Q36–Q38).

These are good demo examples, but individual results should still be inspected. In particular, criminal-case links indicate a relationship recorded in the database; they do not establish guilt.

## Where a normal user may be dissatisfied

### 1. It can silently omit part of a multi-branch answer

Q14, Q25, Q32, and Q33 asked for multiple relationships. The generated query returned one branch in the graph visualization while leaving another requested branch out. Q11 used a stored case-count property instead of counting actual case relationships. Q20 excluded portfolio holders without linked cases. Q26 omitted the requested median and could omit groups without cases. Q27 used one global top-five limit rather than calculating a top five within each party/status group.

This is the highest-risk quality issue: the page may look populated even though it does not answer the whole question.

### 2. Personal profiles are confused with graph traversals

Q1 and Q2 asked for scalar properties on a named person. The model classified them as graph questions and the validator rejected the generated query because it did not contain a labeled relationship path. Users should be able to ask for recorded properties without having to know Cypher or force an unrelated relationship into the query.

### 3. Empty data is ambiguous

Q12, Q15, Q22, and Q35 returned no rows. Q35 also had a relationship-direction error, so its empty result says nothing reliable about whether such cases exist. The other empty results may reflect absent matches or sparse/incomplete fields. The UI should distinguish “no matching records in this dataset” from “query failed,” “field not recorded,” and “dataset coverage unknown.”

### 4. Some useful tasks are rejected or generated incorrectly

Q28’s label-by-label coverage scan was rejected even though it is a valid metadata question. Q31 asked for five relationship hops but the service guard allows at most three. Q40 produced invalid Cypher. Q5 and Q29 returned the wrong display mode; Q29 also lost its party grouping.

### 5. The data is too stale for present-day claims

The newest `source_document_date` reported by the app is 2024-06-09. Only 131 of 18,632 nodes (0.7%) have a recorded source date. A user asking who is currently serving, what the latest party composition is, or for recent office status should not be shown an unqualified current-tense answer from this snapshot.

## Questions that failed or were incomplete

The full exact wording, generated Cypher, response rows, usage metadata, and error messages are preserved in [the per-question results](hard_research_eval_results.json). The question bank is in [hard_research_questions.json](hard_research_questions.json).

- **Clear partial/incomplete:** Q11 portfolio holders/case links; Q14 BJP-to-case-to-Section graph; Q20 portfolio-holder/case/Section totals; Q25 BJP portfolio graph; Q26 State comparison including median and case prevalence; Q27 top Sections within each party/status group; Q32 BJP portfolio plus case branches; Q33 named person with party and cases.
- **Wrong output mode or intent:** Q5 BJP MLA asset-threshold records; Q29 top Gujarat assets by party.
- **Empty:** Q12 field completeness; Q15 INC MLAs in Delhi; Q22 recorded family counts; Q35 pending BJP cases and Sections.
- **Execution or validation error:** Q1 Rahul Gandhi profile; Q2 Narendra Modi profile; Q28 source-date coverage by label; Q31 five-hop path; Q40 case-burden quartiles compared with assets/liabilities.
- **Correctly unsupported:** Q36 current MPs; Q37 spouses; Q38 currently serving officeholders.

## Patterns and likely causes

1. **The model is not consistently preserving the requested output contract.** It can confuse graph visualizations with scalar tables, drop a branch from a multi-branch request, or lose grouping/ranking requirements.
2. **The validator is both too permissive and too restrictive.** It allows plausible-looking partial queries through, while rejecting useful scalar-property and metadata queries.
3. **Neo4j schema semantics are easy for the model to misread.** Relationship direction, labels, optional matches, and stored-count properties versus actual relationship counts matter. A schema inventory alone does not guarantee correct use.
4. **Complexity grows faster than reliability.** Three-hop paths and common aggregations sometimes work. Per-group top-k, multiple optional branches, five-hop evidence paths, and compound statistical requests are weak or rejected.
5. **Data coverage/freshness affects answer quality independently of Gemini.** The model cannot return information that is missing or stale, and an empty result cannot diagnose that by itself.

## Recommended improvement plan

### Priority 1: Make incomplete answers visible

- Require the planner to list every requested entity, filter, relationship branch, grouping, statistic, sort, and limit in a structured plan.
- Validate that the generated Cypher satisfies each item before execution. If it cannot, ask a clarification or state which part was not answered instead of returning a misleading partial graph.
- For graph output, validate that every requested relationship branch is included in the returned node/edge payload, not merely in a separate `MATCH` clause.
- Add examples for optional relationships so asking for all portfolio holders does not silently exclude holders without cases.

### Priority 2: Route question types before Cypher generation

Add explicit modes for named-entity property lookup, graph path, aggregate/table, metadata/coverage, and unsupported/current-data questions. Named-person properties should be served from a known label/property allowlist without requiring a relationship path. Metadata questions such as counts and source-date coverage should use a fixed, safe backend query.

### Priority 3: Constrain generation with schema-aware templates

- Supply exact labels, property types, relationship directions, and a few canonical examples.
- Use parameterized values and a strict label/relationship/property allowlist.
- Prefer templates for common paths: Party → MLA, MLA → CriminalCase, CriminalCase → Section, MLA → Constituency → State, and person → Ministry.
- For distinct counts, calculate each branch independently or use subqueries so joining cases and Sections does not multiply counts.
- Add explicit templates for per-group top-k and null-aware denominators; do not ask the model to improvise these repeatedly.

### Priority 4: Add a result-quality and evidence layer

- Return a short answer/table alongside the graph, with matched count, denominator, missing-value count, and source-date coverage.
- Label empty results as “no matches in this dataset” only after the query succeeds; show a separate notice when relevant fields are sparse or undated.
- Show query interpretation and expandable generated Cypher for transparency, along with the source date.
- State plainly that a `FACES` link is a recorded database association, not a legal finding of guilt.

### Priority 5: Improve data freshness and provenance

- Refresh from authoritative election/affidavit sources and record source document, source date, ingestion date, and election/office term per record.
- Track freshness and completeness by label/property, not just a single global date.
- Do not answer present-tense “currently serving” questions unless the data includes a verified as-of date and term/status field.

### Priority 6: Build a repeatable regression evaluation

- Keep the 40-question suite and save generated Cypher, result mode, rows, latency, token usage, and error category for each run.
- Add verified expected answers for a smaller core set first, then score factual correctness—not only non-empty output.
- Add tests for known failure classes: scalar profiles, optional branches, wrong relationship direction, per-group top-k, null handling, result-mode routing, five-hop requests, and stale-data safeguards.
- Run the suite against a small approved query cache/template set before spending Gemini tokens. Call Gemini only when deterministic routing/templates cannot answer.

## Practical “ready for demo” guidance

Use direct lookup and simple group-comparison examples that have already been inspected against Neo4j. For broader questions, make the UI tell the user what it understood (labels, filters, fields, and grouping) and let them refine the query. Do not claim the system answers “anything,” and do not use current-office or complete-population language until the data is refreshed and coverage is verified.

Before calling a feature production-ready, the most important gates are: verified expected answers for representative questions; no silent partial multi-branch results; correct empty/error distinction; and freshness/provenance visible to the user.

## Evaluation artifacts

- [Summary metrics](hard_research_eval_summary.json)
- [Full per-question report and generated queries](hard_research_eval_results.json)
- [Question bank](hard_research_questions.json)

## Expanded engineering fix guide

This section maps the findings to the current implementation. The main request path is `POST /api/ask` in `main.py`: local unsupported check → Gemini plan/cache → read-only query validator → Neo4j execution → graph/table JSON. The browser consumes that response in `graph.html`. Keep these boundaries explicit; fixes should improve answer quality without weakening read-only safeguards.

### A. Stop partial graph answers from looking complete

**Observed:** The graph response builder in `ask_graph` merges only `path_nodes` and `path_edges` returned by each row. Gemini can write a query with two `MATCH` branches but return `nodes(p)` for just one path. The API then has no indication that the omitted branch was requested.

**Fix:** Have Gemini return a structured *intent manifest* in addition to Cypher, for example:

```json
{
  "result_type": "graph",
  "requested_paths": [
    ["Party", "MEMBER_OF", "MLA"],
    ["MLA", "FACES", "CriminalCase"],
    ["CriminalCase", "UNDER", "Section"]
  ],
  "requested_properties": ["status", "code"],
  "filters": [{"property":"Party.name","operator":"equals","value":"BJP"}],
  "grouping": [], "sort": [], "limit": 50,
  "cypher": "...", "parameters": {}, "explanation": "..."
}
```

Prefer a canonical `paths` return contract in which every requested branch is separately returned and combined by the backend. Validate returned edge types and node-label transitions against the manifest. If a branch was not returned, do not call the answer complete: return a visible partial-answer warning or regenerate once with a correction instruction. Do not blindly retry indefinitely.

**Files:** prompt/schema and plan validation in `main.py` (`GEMINI_PLAN_SCHEMA`, `gemini_cypher_plan`, `validate_readonly_cypher`, `ask_graph`); warning/status display in `graph.html` where results are rendered.

**Acceptance check:** Q14, Q25, Q32, Q33 each show every requested edge branch or a visible “part not returned” warning. They must never silently show only the party-membership branch.

### B. Fix result-type routing and named-person profiles

**Observed:** The plan only allows `graph`, `aggregate`, or `unsupported`. Profile questions Q1/Q2 ask for properties on a named node, but the graph validator requires a relationship-bearing path (`p = ... [relationship]`). A property lookup is valid Cypher but not a traversal.

**Fix:** Introduce `result_type: "records"` or `"entity"` for scalar/property results. Use an allowlisted label and property projection, e.g. find a `Person` or `MLA` by supported name fields, return properties and source fields, and do not require a relationship path. Better still, deterministically route questions matching “for [name], show/list [properties]” to a named-entity query template; send ambiguous requests to Gemini. Add separate output validation: graph requires path payload, records requires scalar columns, aggregate requires scalar grouped values.

Also replace `_question_prefers_aggregate` as the sole example-type heuristic with the structured route. Its regex can misclassify ordinary wording (for example “show the highest…” could request a graph of entities or a scalar aggregate). Put the chosen mode in the plan and validate that the mode matches user intent; if uncertain, ask a small clarification in the UI.

**Files:** `GEMINI_PLAN_SCHEMA` and prompt in `main.py`; validator and `ask_graph` response branching; mode rendering in `graph.html` (currently aggregate and graph branches).

**Acceptance check:** Q1 and Q2 return a row with the requested recorded fields, including nulls as null, without inventing a relationship. A graph request still returns valid node/edge arrays.

### C. Treat empty result as a state that needs explanation

**Observed:** An empty Neo4j result currently becomes a graph with no paths or an aggregate with no rows. That does not distinguish no matching record from incomplete source coverage, wrong generated filter, or a sparse property.

**Fix:** Return explicit fields such as `query_status` (`ok`, `no_matches`, `partial`, `unsupported`, `error`), `matched_rows`, `data_limitations`, and source freshness. For zero rows, provide a safe follow-up: “No matching records were returned from this dataset; that does not establish that none exist.” For property-based aggregates, show non-null denominators and missing counts per requested field. If source coverage for the requested label/property is unknown, say so. Add a deterministic query plan preview so the user can see parsed filters before running.

Do not label all empty results as missing-data cases: Q15 may simply have no matching Delhi record in this dataset, while Q35 had a bad generated relationship direction. The response should expose the generated query and an error category to distinguish them.

**Files:** response construction and error handling in `ask_graph`; freshness from `/api/metadata`; empty/error/partial display in `graph.html`.

**Acceptance check:** Q12, Q15, Q22, and Q35 display different explanations where evidence supports that distinction; none says “there are no such people/cases” solely because rows are empty.

### D. Improve the read-only Cypher validator without relaxing security

**Observed:** `validate_readonly_cypher` uses regular expressions to inspect Cypher. It rejects a useful metadata query with no explicit label (Q28), while still allowing logically incomplete Cypher if it conforms syntactically. Regex checks are not a reliable Cypher parser.

**Fix:** Keep the existing label/property/relationship allowlists and read-only transaction, but split validation into stages:

1. Parse/tokenize Cypher with a maintained Cypher parser if compatible with the deployed Neo4j version; otherwise keep a narrow generated-query grammar and reject anything outside it.
2. Validate identifiers against the allowlists and parameters separately (the current parameterization is good and should remain).
3. Use fixed server-owned templates for metadata/coverage queries. Do not let Gemini author arbitrary `MATCH (n)` scans or reject a safe metadata request simply because it has no label.
4. Enforce row, time, and path bounds server-side. Keep the read-only database role and transaction timeout; never allow a model-supplied timeout or database selection.
5. Add structural checks against the intent manifest (requested labels, edge transitions, fields, grouping and sorting).

Q31 conflicts with the current three-hop cap. Keep that cap for user-generated paths unless there is a concrete use case and query budget. Instead decompose a five-hop request into bounded stages or return a clear explanation that the requested path is beyond the supported depth. Do not simply raise the cap globally.

**Files:** `validate_readonly_cypher` in `main.py`, plus a deterministic metadata handler and structured error responses.

**Acceptance check:** Q28 runs through a fixed metadata query; unsafe clauses remain rejected; Q31 gets an intentional, user-readable depth limitation rather than a generic validator error.

### E. Correct aggregate math and rankings

**Observed:** Q11/Q20 can confuse stored counters with actual relationships or exclude holders without cases. Q26 omits median and optional groups. Q27 returns a global `LIMIT`, not top five inside every group. Q39 risks row multiplication when independent branches are joined.

**Fix:** Implement server-owned aggregate templates for common patterns:

- Compute the base population first (for example all portfolio holders), then `OPTIONAL MATCH` case/Section branches so entities with no cases remain in the denominator.
- Use `count(DISTINCT ...)` for entity counts, but avoid multiplying independent relationships by aggregating branches separately (Neo4j subqueries/`CALL { ... }` if allowed in a fixed template, or separate bounded read queries combined server-side).
- Emit a non-null sample count next to every mean/median. Never imply a missing value is zero.
- For per-group top-k, rank within each group using a supported window/subquery strategy; do not use a single global `LIMIT` as a substitute.
- If a requested statistic is unsupported by the database version or query grammar, return an explicit unsupported component rather than silently omitting it.

First add hand-reviewed templates for Q11, Q20, Q26, Q27, Q30, Q34, and Q39. A stable set of templates is cheaper and more reliable than repeatedly asking Gemini to invent delicate aggregation logic.

**Files:** route/template layer and query execution in `main.py`; aggregate table rendering in `graph.html`.

**Acceptance check:** compare each template result against a separately written direct Neo4j query on a small known fixture; verify totals, denominators, distinct counts, and per-group ranks.

### F. Improve examples and the Gemini prompt with targeted patterns

**Observed:** `select_cypher_examples` selects examples by token overlap, and the prompt includes only a few examples. This can retrieve the right words but the wrong query pattern—for example, a simple case lookup rather than an optional branch or grouped ranking.

**Fix:** Tag each catalog item with structured metadata: intent type, labels, relationship sequence/direction, optional branches, aggregate method, null behavior, and expected result fields. Select examples by those fields after deterministic intent classification, not word overlap alone. Keep a small, curated set of gold examples. Add “near miss” counterexamples for the exact failure classes: path omitted from return, relationship direction reversed, global versus per-group top-k, optional branch accidentally made mandatory, and scalar profile wrongly classified as graph.

The prompt should request a concise plan first and make the model include all requested clauses. Avoid simply making it longer: long schema text consumes tokens and does not replace structural validation. Record prompt version with each evaluation result so changes can be compared.

**Files:** `cypher_examples.json`, `select_cypher_examples`, `GEMINI_PLAN_SCHEMA`, and system prompt in `main.py`.

**Acceptance check:** run the same fixed question set before/after; compare exact intent fields, query validity, completeness, token count, and latency. Only keep a prompt/example change if correctness improves without unacceptable token cost.

### G. Make freshness and provenance actionable

**Observed:** `/api/metadata` reports a global latest date and fraction of nodes with a source date. That is useful but does not identify which source supports a particular field or whether a specific MLA record is current.

**Fix:** During ingestion, persist for each imported record: source URL/document, published/effective date, retrieval date, election year/term, and a stable entity ID. Track property-level source coverage and freshness by label. On display, attach provenance to the node/property or table row, and show “recorded as of” rather than “current.” Implement a refresh workflow that first stages new source data, reports changed/missing records, then merges only after validation. Use authoritative sources such as the Election Commission and official legislature/member records; preserve source citations in Neo4j.

Do not let the LLM determine current office status from an election year. Add a server rule: current-tense questions are answerable only when a verified status and valid-as-of date exist for the matching record; otherwise return unsupported/stale.

**Files:** primarily ingestion scripts and Neo4j constraints/indexes; `/api/metadata` in `main.py`; provenance display in `graph.html`. The UI already shows a freshness note, so extend it with record-level citations rather than hiding it.

**Acceptance check:** a displayed profile/case has a clickable source and date; a current-office question is refused if the record has no valid current-status evidence.

### H. Add an evaluation loop that measures truth and user experience

**Observed:** Current score is based on expected output type and non-empty rows, then manual shape review. This catches some failures but cannot establish factual accuracy or whether a result is useful to a normal user.

**Fix:** Create a smaller verified core suite (start with 20–30 questions) where each expected answer is independently checked against Neo4j and an authoritative source where applicable. Store expected entity IDs, counts, fields, and paths—not just a prose answer. Score separate dimensions:

- routing/result mode correct;
- Cypher valid and read-only;
- requested filters/paths/statistics all represented;
- returned IDs/counts match the gold result;
- provenance/freshness disclosed when needed;
- end-user usefulness (clear language, not misleading on empty/partial data).

Keep complex questions as stress tests, but do not mix them into a single pass percentage with straightforward questions. Save model/version, prompt version, token counts, latency, errors, result IDs, and reviewer notes. Compare regressions after each prompt, template, or data update.

The production demo should surface friendly errors while server logs retain a safe diagnostic ID and error class. Never log API secrets or send them to the browser.

**Acceptance check:** every change has before/after results on the fixed suite; core questions do not regress; new failures are classified and reproducible.

## Suggested implementation order

1. **Immediate reliability:** introduce explicit status and partial-answer behavior; fix graph branch completeness checks; route scalar named-person lookups.
2. **Query correctness:** add fixed templates for common aggregates and metadata coverage; fix optional matches, distinct counts, and grouped top-k.
3. **Explainability:** expose interpreted intent, result counts, missing-value denominators, and provenance in the UI.
4. **Data quality:** refresh records and add source/as-of metadata; only then enable current-office questions.
5. **Measured iteration:** establish gold answers and rerun regression suite after every change.

This order addresses the most damaging user experience first: a confident-looking but incomplete result. It also reduces Gemini spend because repeated query forms use deterministic templates or the existing plan cache, while hard questions are sent to Gemini only when needed.

