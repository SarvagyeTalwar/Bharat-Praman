# Person-only ministry nodes — proposed review table (no DB writes)

These 28 `Person` nodes carry only `name`, `council_section` and `source_document_date`
(2024-06-09, Union Council of Ministers). They have no `entity_id`, no MP/MLA label, no
constituency, and no affidavit data. They are **not** being merged or linked in Phase 1.

Below is a proposed mapping to existing MP/MLA nodes for human review. "Exact" = same name
ignoring punctuation/order; "Likely" = spelling or initial-expansion variant. No link has been
created.

| # | Person-only name | Council section | Proposed existing node | Basis | Notes |
|---|---|---|---|---|---|
| 1 | G. Kishan Reddy | Cabinet Minister | sansad_mp_5084 G Kishan Reddy (MP) | exact | |
| 2 | H. D. Kumaraswamy | Cabinet Minister | sansad_mp_3711 H D Kumaraswamy (MP) | exact | |
| 3 | Jadhav Prataprao Ganpatrao | MoS (Independent Charge) | sansad_mp_4373 Prataprao Ganpatrao Jadhav (MP) | exact (token order) | |
| 4 | Jyotiraditya M. Scindia | Cabinet Minister | sansad_mp_3958 Jyotiraditya M Scindia (MP) | exact | |
| 5 | Kirtivardhan Singh | Minister of State | sansad_mp_3926 Kirti Vardhan Singh (MP) | exact (spacing) | |
| 6 | Krishan Pal | Minister of State | sansad_mp_4629 Krishan Pal Gurjar (MP) | likely | prefix; verify |
| 7 | Raj Nath Singh | Cabinet Minister | sansad_mp_4268 Rajnath Singh (MP) | exact (spacing) | |
| 8 | S. P. Singh Baghel | Minister of State | sansad_mp_31 S P Singh Baghel (MP) | exact | |
| 9 | V. Somanna | Minister of State | sansad_mp_5625 V Somanna (MP) | exact | |
| 10 | Pankaj Chaudhary | Minister of State | sansad_mp_3479 Pankaj Choudhary (MP) | likely | spelling variant; verify |
| 11 | Durgadas Uikey | Minister of State | sansad_mp_5057 Durgadas D D Uikey (MP) | likely | initial expansion |
| 12 | Bhupathi Raju Srinivasa Varma | Minister of State | sansad_mp_5745 Srinivasa Varma B J P Varma Bhupathiraju (MP) | likely | token order; verify |
| 13 | C R Patil | Cabinet Minister | sansad_mp_4452 Chandrakant Raghunath Patil (MP) | likely | initials expanded; verify |
| 14 | Ashwini Vaishnaw | Cabinet Minister | — | none | Rajya Sabha minister |
| 15 | Nirmala Sitharaman | Cabinet Minister | — | none | Rajya Sabha minister |
| 16 | Subrahmanyam Jaishankar | Cabinet Minister | — | none | Rajya Sabha minister |
| 17 | Piyush Goyal | Cabinet Minister | — | none | Rajya Sabha minister |
| 18 | Hardeep Singh Puri | Cabinet Minister | — | none | Rajya Sabha minister |
| 19 | Jagat Prakash Nadda | Cabinet Minister | — | none | Rajya Sabha minister |
| 20 | B. L. Verma | Minister of State | — | none | Rajya Sabha minister |
| 21 | George Kurian | Minister of State | — | none | Rajya Sabha minister |
| 22 | Jayant Chaudhary | MoS (Independent Charge) | — | none | Rajya Sabha minister |
| 23 | L. Murugan | Minister of State | — | none | Rajya Sabha minister |
| 24 | Pabitra Margherita | Minister of State | — | none | Rajya Sabha minister |
| 25 | Ram Nath Thakur | Minister of State | — | none | Rajya Sabha minister |
| 26 | Ramdas Athawale | Minister of State | — | none | Rajya Sabha minister |
| 27 | Ravneet Singh | Minister of State | — | none | Rajya Sabha minister |
| 28 | Satish Chandra Dubey | Minister of State | — | none | Rajya Sabha minister |

Next step (not done): for rows 1–13, confirm identity and, if approved, attach the ministry
office to the existing MP node (e.g. a `HOLDS_PORTFOLIO` link with source/document date) instead
of keeping a duplicate Person. Waiting for explicit approval before any write.
