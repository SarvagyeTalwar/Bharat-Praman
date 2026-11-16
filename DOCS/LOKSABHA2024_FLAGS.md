# Lok Sabha 2024 election-label flags (review only, no data changed)

Generated during Phase 1 (Affidavit creation) on 2026-11-08.

Method: for each of the 540 `Person:MP` nodes, the myneta.info `LokSabha2024` candidate page was
located by the stored `myneta_id` (486 from the local cache, 58 fetched with >=2 s throttling) and
compared on name, party, constituency and total assets. All 540 pages responded; the winners index
(`index.php?action=show_winners`) returned 486 ids and was used only as a secondary signal.

Result: 537 pages match the node (name variants aside); 3 nodes are flagged below. Their derived
`LokSabha2024` election label is recorded with `election_verified = false`; nothing was rewritten.

| entity_id | name | constituency | myneta_id | finding | action |
|---|---|---|---|---|---|
| sansad_mp_5836 | Priyanka Gandhi Vadra | Wayanad | (none) | No affidavit data at all (no myneta_id, no assets, no cases). Wayanad was vacated in 2024 and filled in a by-election. Page not in LokSabha2024 winners index. | Flagged only; affidavit created with null amounts, `election_verified=false`, `election_source="derived: sansad_mp_5836, 18th Lok Sabha"`. Needs a by-election-specific affidavit before any asset claim is made. |
| sansad_mp_5835 | Chavan Ravindra Vasantrao | Nanded | 1782 | `myneta_id=1782` resolves to **Vasantrao Balwantrao Chavan (INC)**, the 2024 general-election winner, not Ravindra Chavan (by-election winner). Assets on the node equal that page (Rs 3,67,85,180), so the affidavit belongs to the predecessor, not to this person. | Flagged only; `election_verified=false`; the node/affidavit identity mismatch needs manual correction (do not silently relabel). |
| sansad_mp_5584 | G Lakshminarayana | Anantapur | (none) | No affidavit data (no myneta_id, no assets, no cases); page not found. Could not be verified. | Flagged only; affidavit created with null amounts, `election_verified=false`. |

Notes:
- None of the three is presented as a verified 2024 general-election affidavit.
- The 24 spot-checked MPs that matched are marked `election_verified=true` on their affidavits and
  on the `FOR_ELECTION` / `CONTESTED` links; every other MP stays `false`.
- Spelling/order variants found by the scan (e.g. CHOUDHARY/CHAUDHARY, Hema Malini/HEMAMALINI
  DHARMENDRA DEOL) were treated as the same person; they are not listed here.
