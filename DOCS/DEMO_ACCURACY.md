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
