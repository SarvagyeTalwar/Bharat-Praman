# MLA ingest — summary (Instance01)

## Elections added (11)
| election_id | year | state | MLAs |
|---|---|---|---|
| Orissa2004 | 2004 | Odisha | 128 |
| Orissa2009 | 2009 | Odisha | 120 |
| TamilNadu2011 | 2011 | Tamil Nadu | 200 |
| Haryana2014 | 2014 | Haryana | 80 |
| Odisha2014 | 2014 | Odisha | 130 |
| TamilNadu2016 | 2016 | Tamil Nadu | 194 |
| UttarPradesh2017 | 2017 | Uttar Pradesh | 359 |
| Haryana2019 | 2019 | Haryana | 80 |
| Odisha2019 | 2019 | Odisha | 130 |
| TamilNadu2021 | 2021 | Tamil Nadu | 200 |
| TamilNadu2026 | 2026 | Tamil Nadu | 208 |

Source: myneta.info winners index (`index.php?action=show_winners`) + per-candidate pages for age,
liabilities, asset split, profession and criminal cases.

## Graph impact (this work only)
- Nodes: 1,829 Person + 1,829 Affidavit + 1,829 AssemblyConstituency + 11 Election + 11 Party
  + 3,058 CriminalCase + 174 Section = **8,741**
- Relationships: 1,829 each of FILED / FOR_ELECTION / CONTESTED / REPRESENTS / MEMBER_OF / IN_STATE,
  3,058 each of FACES / DISCLOSES, 9,895 UNDER = **27,785**

## Coverage gaps
- Winners index lists ~85–90% of seats. Missing seats per election:
  UP2017 44, TN2016 40, TN2011 34, TN2021 34, Orissa2009 27, TN2026 26, Orissa2004 19,
  OD2014 17, OD2019 17, HR2014 10, HR2019 10 (**278 total**).
- Elections absent from myneta: Haryana 2009/2004, Tamil Nadu 2006, UP 2012/2007/2002.
- Gender: not exposed on myneta MLA pages (1,829 null).
- Profession: 278 pages have no profession field.
- Assets: 2 MLAs have no declared figure (Hrushikesh Naik 2009, Ajit Hembram 2004).
- Case rows: 2 anomalies (Duraimurugan 8 declared vs 6 parsed; M. Jagan Moorthy 2 vs 3).
- TN 2011: myneta's 2011 pages say "No criminal cases" for all entries (source limitation).

## Timelines
315 strict repeat-MLA careers (same state + name + shared seat): 9 with 4 elections, 28 with 3,
278 with 2. Full list in `DOCS/MLA_TIMELINES.md`; machine-readable in `data/mla_timelines.json`.

## Re-run order
1. `scripts/mla_ingest/fetch_winners.py` — download winners indexes
2. `scripts/mla_ingest/parse_winners.py` — parse to `mla_winners_parsed.json`
3. `scripts/mla_ingest/ingest_mla_new.py [--write]` — create Election/Person/Affidavit/links
4. `scripts/mla_ingest/fetch_async.py` — fetch candidate pages (resumable cache)
5. `scripts/mla_ingest/enrich_mla.py [--write]` — fill age/liabilities/assets/cases
6. `scripts/mla_ingest/build_timelines_strict.py` — rebuild timelines
