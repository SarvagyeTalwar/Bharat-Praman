(function () {
  "use strict";

  const SCENARIOS = [
    {
      id: 0,
      question: "Compare BE vs RE for MGNREGA and PMGSY over 4 years",
      latency: "184 ms graph + vector",
      graphBadge: "AuraDB Vector + BudgetLineItem",
      graphPath: "MoRD -> BudgetDoc (FY22-FY25) -> NEXT_YEAR -> BudgetTable",
      badgeText: "Provenance Verified",
      steps: [
        "Resolving Rural Development & scheme nodes",
        "Traversing NEXT_YEAR budget document chain",
        "Locking Rs. Crore units & table footnotes",
        "Verifying primary pages & missing splits"
      ],
      summary:
        "Across FY21-22 through FY24-25, GraphRAG links Demand for Grants and Expenditure Vol I tables chronologically via [:NEXT_YEAR] edges. Revised Estimates (RE) and Budget Estimates (BE) remain separated per scheme line item in Rs. Crore, preserving wage-material and capital works footnotes verbatim.",
      tableHead: ["Document Source", "FY", "Section / Head", "Unit Lock"],
      tableRows: [
        ["mof_exp_vol1_2024-25.pdf", "2024-25", "Rural Dev · Page 88", "Rs. in Crore"],
        ["mof_outcome_2024-25.pdf", "2024-25", "PMGSY / MGNREGA KPIs", "Rs. in Crore"],
        ["mof_allsbe_2023-24.pdf", "2023-24", "Statement 1 · Exp", "Rs. in Crore"]
      ],
      sourcesText: "Sources: Union Expenditure Vol I, Outcome Budgets (MoF / MoRD)",
      caveatText: "Actuals for current year marked Not Disclosed until CAG release",
      nodes: [
        { id: "mord", type: "Ministry", label: "Rural Dev (MoRD)", x: 16, y: 134, highlight: true, props: { code: "MoRD", portfolio: "Rural Development", corpus_fy: "2021-22..2025-26" } },
        { id: "doc1", type: "BudgetDoc", label: "Exp Vol I (FY24-25)", x: 204, y: 46, props: { file: "mof_exp_vol1_2024-25.pdf", page: 88, unit: "Rs. in Crore" } },
        { id: "doc2", type: "BudgetDoc", label: "Outcome (FY24-25)", x: 204, y: 218, props: { file: "mof_outcome_2024-25.pdf", chunks: 873, estimates: "BE / RE" } },
        { id: "s1", type: "Scheme", label: "MGNREGA", x: 398, y: 46, highlight: true, props: { canonical: "MGNREGA", estimate_lock: "BE vs RE separated", linked_years: 4 } },
        { id: "s2", type: "Scheme", label: "PMGSY", x: 398, y: 218, highlight: true, props: { canonical: "PMGSY", unit: "Rs. in Crore", category: "Capital / Grants" } }
      ],
      edges: [
        { from: "mord", to: "doc1", rel: "HAS_BUDGET" },
        { from: "mord", to: "doc2", rel: "HAS_OUTCOME" },
        { from: "doc1", to: "doc2", rel: "CORROBORATES" },
        { from: "doc1", to: "s1", rel: "FOR_SCHEME" },
        { from: "doc2", to: "s2", rel: "TRACKS_KPI" }
      ]
    },
    {
      id: 1,
      question: "How did PM-SHRI and Samagra Shiksha targets evolve?",
      latency: "142 ms graph + RRF",
      graphBadge: "AuraDB AnnualReport + NEXT_YEAR",
      graphPath: "MoE -> AnnualReport (FY22-FY26) -> Section -> Scheme",
      badgeText: "4-Year Lineage Cited",
      steps: [
        "Resolving Ministry of Education & scheme aliases",
        "Interleaving balanced chunks across 5 FYs",
        "Attaching [Chapter | Scheme | Unit] headers",
        "Checking physical target vs rollout caveats"
      ],
      summary:
        "Stratified retrieval balances chunks evenly across FY21-22 to FY25-26 Ministry of Education reports (9,660 indexed chunks). Chronological [:NEXT_YEAR] traversal separates initial PM-SHRI framework milestones from later school-upgradation phases and preserves teacher vacancy footnotes.",
      tableHead: ["Document Source", "FY", "Chunks", "Scope"],
      tableRows: [
        ["moe25-26.pdf", "2025-26", "253", "School Edu Outcomes"],
        ["moe24-25.pdf", "2024-25", "969", "PM-SHRI & Samagra"],
        ["moe23-24.pdf + udise", "2023-24", "1,436+", "UDISE & Rollout"]
      ],
      sourcesText: "Sources: moe21-22.pdf through moe25-26.pdf (Ministry of Education)",
      caveatText: "District splits absent in report flagged as Not Disclosed",
      nodes: [
        { id: "moe", type: "Ministry", label: "Education (MoE)", x: 16, y: 134, highlight: true, props: { code: "MoE", ingested_docs: 12, ingested_chunks: 9660 } },
        { id: "r23", type: "AnnualReport", label: "MoE Report 23-24", x: 204, y: 46, props: { file: "moe23-24.pdf", chunks: 896, linked_next: "moe24-25.pdf" } },
        { id: "r25", type: "AnnualReport", label: "MoE Report 24-25", x: 204, y: 218, props: { file: "moe24-25.pdf", chunks: 969, unit_freeze: true } },
        { id: "pm", type: "Scheme", label: "PM-SHRI", x: 398, y: 46, highlight: true, props: { acronym: "PM-SHRI", ministry: "Education", provenance: "Page-pinned" } },
        { id: "ss", type: "Scheme", label: "Samagra Shiksha", x: 398, y: 218, highlight: true, props: { acronym: "Samagra Shiksha", footnotes_bound: true } }
      ],
      edges: [
        { from: "moe", to: "r23", rel: "PUBLISHED" },
        { from: "r23", to: "r25", rel: "NEXT_YEAR" },
        { from: "r23", to: "pm", rel: "MENTIONS" },
        { from: "r25", to: "pm", rel: "UPDATES", labelT: 0.34 },
        { from: "r25", to: "ss", rel: "ALLOCATES" }
      ]
    },
    {
      id: 2,
      question: "Cross-check our policy brief against MHA & MoD reports",
      latency: "168 ms RBAC + vector",
      graphBadge: "Tenant Isolation Enforced",
      graphPath: "Private Tenant (Encrypted) -> Clause -> MHA & MoD Spine",
      badgeText: "Zero External Egress",
      steps: [
        "Injecting tenant_id & clearance predicates",
        "Chunking uploaded brief via local BGE-small",
        "Bridging private clauses to MHA & MoD nodes",
        "Generating isolated citation ledger"
      ],
      summary:
        "Uploaded internal policy briefs or DPRs stay strictly scoped to your Neo4j Aura tenant_id and clearance level. Local embeddings align your draft clauses to 6,907 public MHA & Defence chunks without transmitting your private document to any external model training pipeline.",
      tableHead: ["Subgraph Scope", "Documents", "Chunks", "Access Mode"],
      tableRows: [
        ["tenant: org_internal", "Uploaded Brief", "Local 384-d", "Strictly Isolated"],
        ["public: Home Affairs", "mha22-25.pdf (3)", "2,247", "Read-Only Spine"],
        ["public: Defence", "def23-25.pdf (5)", "4,660", "Read-Only Spine"]
      ],
      sourcesText: "Sources: Tenant Subgraph + MHA/MoD Annual Reports (2022-25)",
      caveatText: "AST Read-Only Cypher blocks cross-tenant node traversal",
      nodes: [
        { id: "priv", type: "PrivateTenant", label: "Org Policy Brief", x: 16, y: 134, private: true, highlight: true, props: { tenant_id: "org_client_01", clearance: "Level 2 Restricted", embed_model: "BAAI/bge-small-en-v1.5" } },
        { id: "cl", type: "PrivateTenant", label: "Clause Chunk #14", x: 204, y: 46, private: true, props: { tenant_id: "org_client_01", vector_dim: 384, training_egress: false } },
        { id: "mha", type: "AnnualReport", label: "MHA Report 24-25", x: 204, y: 218, props: { file: "mha24-25.pdf", chunks: 844, scope: "public" } },
        { id: "mod", type: "AnnualReport", label: "MoD Report 24-25", x: 398, y: 46, props: { file: "def24-25.pdf", chunks: 415, scope: "public" } },
        { id: "cyb", type: "Topic", label: "Border & Cyber", x: 398, y: 218, highlight: true, props: { entities: "I4C / BSF / iDEX", matched_via: "Cosine RRF" } }
      ],
      edges: [
        { from: "priv", to: "cl", rel: "HAS_CHUNK", isolated: true },
        { from: "cl", to: "mod", rel: "TENANT_MATCH", isolated: true },
        { from: "priv", to: "mha", rel: "TENANT_MATCH", isolated: true },
        { from: "mod", to: "cyb", rel: "MENTIONS" },
        { from: "mha", to: "cyb", rel: "MENTIONS" }
      ]
    },
    {
      id: 3,
      question: "Defence capex vs Home Affairs modernisation since 2022",
      latency: "196 ms structured SQL+Graph",
      graphBadge: "Capex vs Revenue Split Lock",
      graphPath: "MoD + MHA -> BudgetDoc (FY22-FY25) -> Capital vs Revenue",
      badgeText: "Units Locked Verbatim",
      steps: [
        "Separating Defence Services & MHA grants",
        "Filtering Capital Outlay vs Revenue heads",
        "Binding Demand for Grants annexure notes",
        "Verifying comparable multi-year baseline"
      ],
      summary:
        "Combines Ministry of Finance Demands for Grants (mof_alldg) with Defence and MHA Annual Reports to keep Capital Acquisition heads strictly separated from Revenue, Pay, and Defence Pensions—preventing misleading aggregate comparisons.",
      tableHead: ["Domain", "Primary Series", "Indexed Scope", "Head Separation"],
      tableRows: [
        ["Defence (MoD)", "def23-25.pdf + AllDG", "4,660 chunks", "Capital vs Pensions"],
        ["Home Affairs (MHA)", "mha22-25.pdf + AllDG", "2,247 chunks", "CAPF Modernisation"],
        ["Finance Cross-Check", "mof_exp_vol1_21-25", "27,886 chunks", "Verifiable Be/RE"]
      ],
      sourcesText: "Sources: MoF Demands for Grants, MoD & MHA Reports (FY22-25)",
      caveatText: "Classified sub-item operational breakdowns marked Not Disclosed",
      nodes: [
        { id: "mof", type: "Ministry", label: "Finance (AllDG)", x: 16, y: 134, highlight: true, props: { code: "MoF", ingested_docs: 29, chunks: 27886 } },
        { id: "def", type: "Ministry", label: "Defence (MoD)", x: 204, y: 46, props: { file: "def24-25.pdf", capital_head: "Separated", drdo: true } },
        { id: "mha", type: "Ministry", label: "Home Affairs (MHA)", x: 204, y: 218, props: { file: "mha24-25.pdf", capf: "CRPF / BSF", border_infra: true } },
        { id: "cap", type: "BudgetTable", label: "Capital Outlay", x: 398, y: 46, highlight: true, props: { head: "Capital Acquisition", unit: "Rs. in Crore" } },
        { id: "rev", type: "BudgetTable", label: "Revenue & Pensions", x: 398, y: 218, props: { head: "Revenue / Pay", rule: "Never merged silently" } }
      ],
      edges: [
        { from: "mof", to: "def", rel: "FUNDS_GRANT" },
        { from: "mof", to: "mha", rel: "FUNDS_GRANT" },
        { from: "def", to: "cap", rel: "HAS_TABLE" },
        { from: "def", to: "rev", rel: "SEPARATES", labelT: 0.24 },
        { from: "mha", to: "cap", rel: "CAPF_CAPEX", labelT: 0.24 }
      ]
    }
  ];

  const EXTRA_PROMPTS = {
    "What changed in Ayushman Bharat since 2022?": {
      id: "custom-pmjay",
      question: "What changed in Ayushman Bharat since 2022?",
      latency: "156 ms graph + RRF",
      graphBadge: "MoHFW + Budget Outcome Bridge",
      graphPath: "MoF Outcome + MoHFW -> Scheme (PM-JAY / AIIMS) -> FY22-FY25",
      badgeText: "Provenance Verified",
      steps: [
        "Resolving PM-JAY, NHM & AIIMS acronyms",
        "Scanning MoF Outcome & Expenditure Vols",
        "Checking MoHFW corpus coverage status",
        "Assembling citation-locked summary"
      ],
      summary:
        "Across Finance Outcome Budgets and Expenditure statements (2021-22 to 2025-26), PM-JAY and AIIMS capital lines show explicit BE/RE progression. Notice: standalone MoHFW Annual Report PDFs are queued in the next batch—so Ministry narrative nuances absent in Finance tables are transparently marked pending.",
      tableHead: ["Dataset Layer", "Status", "FY Coverage", "Disclosure Note"],
      tableRows: [
        ["Finance Outcome Budgets", "Live Indexed", "2021-22 — 2025-26", "Physical + Financial KPIs"],
        ["Demand for Grants (MoF)", "Live Indexed", "2021-22 — 2025-26", "Exact BE vs RE in Crore"],
        ["MoHFW Annual Reports", "Ontology Ready", "4-Year Queue", "Marked Pending Explicitly"]
      ],
      sourcesText: "Sources: mof_outcome_2022-26.pdf, mof_allsbe_2022-26.pdf",
      caveatText: "Coverage gap for standalone MoHFW annual reports shown honestly",
      nodes: [
        { id: "mof", type: "Ministry", label: "Finance Outcomes", x: 16, y: 134, highlight: true, props: { docs: 29, series: "Outcome + SBE 21-26" } },
        { id: "pmj", type: "Scheme", label: "Ayushman (PM-JAY)", x: 204, y: 46, highlight: true, props: { alias: "PM-JAY", status: "Tracked via MoF Outcome" } },
        { id: "aim", type: "Scheme", label: "AIIMS Outlays", x: 204, y: 218, props: { category: "Tertiary Health Infra", unit: "Rs. in Crore" } },
        { id: "moh", type: "Ministry", label: "MoHFW (Queue)", x: 398, y: 134, props: { state: "Batch Queue", behavior: "Explicit Gap Flag" } }
      ],
      edges: [
        { from: "mof", to: "pmj", rel: "REPORTS_OUTCOME" },
        { from: "mof", to: "aim", rel: "ALLOCATES_RE" },
        { from: "moh", to: "pmj", rel: "OWNING_MINISTRY" }
      ]
    },
    "Which agriculture schemes saw mid-year RE cuts?": {
      id: "custom-agri",
      question: "Which agriculture schemes saw mid-year RE cuts?",
      latency: "162 ms Budget Graph",
      graphBadge: "BudgetLineItem BE vs RE Variance",
      graphPath: "MoAFW + MoF AllSBE -> BudgetLineItem (RE < BE) -> Footnotes",
      badgeText: "Unit Precision Locked",
      steps: [
        "Resolving PM-KISAN & PMFBY scheme keys",
        "Comparing BE vs RE columns verbatim",
        "Checking mof_allsbe & Exp Vol I footnotes",
        "Flagging corpus boundary caveats"
      ],
      summary:
        "Structural table extraction compares Budget Estimate (BE) directly against Revised Estimate (RE) on each Union Expenditure line item without rounding. Where MoAFW standalone annual reports await batch indexing, results cite Finance AllSBE & Outcome Budget volumes directly.",
      tableHead: ["Scheme Identifier", "Verification Basis", "Unit Lock", "Status"],
      tableRows: [
        ["PM-KISAN", "Finance AllSBE + Outcome", "Rs. in Crore", "Variance Auditable"],
        ["PMFBY (Crop Ins.)", "Finance AllSBE + Outcome", "Rs. in Crore", "Variance Auditable"],
        ["MoAFW Annual Reports", "Queued Ingestion", "Batch Pipeline", "Disclosure Marked"]
      ],
      sourcesText: "Sources: mof_allsbe_2021-26.pdf, mof_outcome_2021-26.pdf",
      caveatText: "Only primary Finance budget lines cited until MoAFW PDFs commit",
      nodes: [
        { id: "sbe", type: "BudgetDoc", label: "AllSBE (FY22-26)", x: 16, y: 134, highlight: true, props: { file: "mof_allsbe_2024-25.pdf", chunks: 1238 } },
        { id: "kis", type: "Scheme", label: "PM-KISAN", x: 204, y: 46, highlight: true, props: { scheme: "PM-KISAN", metric: "RE - BE Variance" } },
        { id: "fby", type: "Scheme", label: "PMFBY Crop Ins.", x: 204, y: 218, highlight: true, props: { scheme: "PMFBY", unit: "Rs. in Crore" } },
        { id: "agr", type: "Ministry", label: "MoAFW", x: 398, y: 134, props: { code: "MoAFW", queue: "Annual Report Batch" } }
      ],
      edges: [
        { from: "sbe", to: "kis", rel: "CONTAINS_ITEM" },
        { from: "sbe", to: "fby", rel: "CONTAINS_ITEM" },
        { from: "agr", to: "kis", rel: "ADMINISTERS" },
        { from: "agr", to: "fby", rel: "ADMINISTERS" }
      ]
    },
    "Trace DRDO and iDEX defence priorities across 4 years": {
      id: "custom-mod",
      question: "Trace DRDO and iDEX defence priorities across 4 years",
      latency: "149 ms graph + vector",
      graphBadge: "MoD Annual Report Graph",
      graphPath: "MoD -> AnnualReport (def23-25) -> Chunk -> DRDO / iDEX",
      badgeText: "4,660 MoD Chunks",
      steps: [
        "Expanding DRDO, iDEX & Agnipath glossary",
        "Querying bge_chunk_embeddings on MoD",
        "Ranking exact acronym matches via RRF",
        "Attaching page numbers & footnotes"
      ],
      summary:
        "Lexical + BGE-small RRF ranking pulls exact scheme and innovation passages from five Ministry of Defence reports (def.pdf, def1.pdf, def23-24.pdf, def24-25.pdf, def25-24.pdf — totaling 4,660 indexed chunks) while preserving chapter hierarchy.",
      tableHead: ["Indexed Document", "Fiscal Year", "Chunks", "Coverage Focus"],
      tableRows: [
        ["def24-25.pdf", "2024-25", "415", "MoD Annual Overview"],
        ["def25-24.pdf", "2024-25", "544", "Defence Production"],
        ["def1.pdf + def23-24.pdf", "2023-24", "3,663", "DRDO & Indigenisation"]
      ],
      sourcesText: "Sources: Ministry of Defence Annual Reports (FY23-24, FY24-25)",
      caveatText: "FY21-22 MoD archive in batch queue; scope limited to 23-25 here",
      nodes: [
        { id: "mod", type: "Ministry", label: "Defence (MoD)", x: 16, y: 134, highlight: true, props: { ingested_docs: 5, chunks: 4660 } },
        { id: "d23", type: "AnnualReport", label: "MoD Report 23-24", x: 204, y: 46, props: { file: "def1.pdf", chunks: 3371 } },
        { id: "d24", type: "AnnualReport", label: "MoD Report 24-25", x: 204, y: 218, props: { file: "def24-25.pdf", chunks: 415 } },
        { id: "drd", type: "Organization", label: "DRDO & iDEX", x: 398, y: 134, highlight: true, props: { acronyms_resolved: true, rrf_boost: "Exact Match" } }
      ],
      edges: [
        { from: "mod", to: "d23", rel: "PUBLISHED" },
        { from: "d23", to: "d24", rel: "NEXT_YEAR" },
        { from: "d23", to: "drd", rel: "MENTIONS" },
        { from: "d24", to: "drd", rel: "UPDATES" }
      ]
    },
    "Summarize border fencing targets from MHA reports": {
      id: "custom-mha",
      question: "Summarize border fencing targets from MHA reports",
      latency: "138 ms graph + RRF",
      graphBadge: "MHA 3-Year Continuity",
      graphPath: "MHA -> MHADocument (22-25) -> Border Management -> Chunk",
      badgeText: "2,247 MHA Chunks",
      steps: [
        "Resolving Border Management & CAPF nodes",
        "Traversing mha22-23 -> mha23-24 -> mha24-25",
        "Preserving length/unit metrics verbatim",
        "Citing chapter & page provenance"
      ],
      summary:
        "Traverses three consecutive Ministry of Home Affairs Annual Reports (mha22-23.pdf, mha23-24.pdf, mha24-25.pdf — 2,247 indexed chunks) linking Border Management chapters and Force modernisation sections with explicit page boundaries.",
      tableHead: ["Indexed Document", "Fiscal Year", "Chunks", "Domain"],
      tableRows: [
        ["mha24-25.pdf", "2024-25", "844", "Border & Cyber Security"],
        ["mha23-24.pdf", "2023-24", "851", "CAPF & Left Wing Ext."],
        ["mha22-23.pdf", "2022-23", "552", "Border Infra Baseline"]
      ],
      sourcesText: "Sources: mha22-23.pdf, mha23-24.pdf, mha24-25.pdf",
      caveatText: "Sensitive operational coordinates absent in public reports marked Not Disclosed",
      nodes: [
        { id: "mha", type: "Ministry", label: "Home Affairs (MHA)", x: 16, y: 134, highlight: true, props: { ingested_docs: 3, chunks: 2247 } },
        { id: "m22", type: "AnnualReport", label: "mha22-23.pdf", x: 204, y: 46, props: { chunks: 552, year: "2022-23" } },
        { id: "m24", type: "AnnualReport", label: "mha24-25.pdf", x: 204, y: 218, props: { chunks: 844, year: "2024-25" } },
        { id: "brd", type: "Topic", label: "Border Management", x: 398, y: 134, highlight: true, props: { forces: "BSF / ITBP / SSB", breadcrumb_locked: true } }
      ],
      edges: [
        { from: "mha", to: "m22", rel: "PUBLISHED" },
        { from: "m22", to: "m24", rel: "NEXT_YEAR" },
        { from: "m22", to: "brd", rel: "REPORTS_ON" },
        { from: "m24", to: "brd", rel: "UPDATES" }
      ]
    }
  };

  // DOM References
  const searchInput = document.getElementById("heroSearchInput");
  const typingCaret = document.getElementById("typingCaret");
  const heroQueryForm = document.getElementById("heroQueryForm");
  const scenarioBtns = Array.from(document.querySelectorAll(".scenario-btn"));
  const chipBtns = Array.from(document.querySelectorAll(".chip-btn"));
  const loopToggleBtn = document.getElementById("loopToggleBtn");
  const loopStateText = document.getElementById("loopStateText");

  const pipelineLatency = document.getElementById("pipelineLatency");
  const pipelineProgressFill = document.getElementById("pipelineProgressFill");
  const stepEls = Array.from(document.querySelectorAll(".pipeline-step"));

  const ragOutputCard = document.getElementById("ragOutputCard");
  const ragGraphPath = document.getElementById("ragGraphPath");
  const ragBadge = document.getElementById("ragBadge");
  const ragSummaryText = document.getElementById("ragSummaryText");
  const ragTableHead = document.getElementById("ragTableHead");
  const ragTableBody = document.getElementById("ragTableBody");
  const ragSourcesText = document.getElementById("ragSourcesText");
  const ragCaveatText = document.getElementById("ragCaveatText");

  const graphBadgeText = document.getElementById("graphBadgeText");
  const svgEdgesLayer = document.getElementById("svgEdgesLayer");
  const svgNodesLayer = document.getElementById("svgNodesLayer");
  const inspectorLabel = document.getElementById("inspectorLabel");
  const inspectorProps = document.getElementById("inspectorProps");

  // State
  let activeScenarioIdx = 0;
  let isAutoLooping = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let timers = [];

  function clearTimers() {
    while (timers.length) {
      clearTimeout(timers.pop());
    }
  }

  function schedule(fn, ms) {
    const id = setTimeout(fn, ms);
    timers.push(id);
    return id;
  }

  function updateLoopUi() {
    loopToggleBtn.textContent = isAutoLooping ? "Pause Loop" : "Resume Loop";
    loopStateText.textContent = isAutoLooping ? "AUTO DEMO ACTIVE" : "INTERACTIVE MODE";
    typingCaret.classList.toggle("hidden", !isAutoLooping);
  }

  function createSvgCheckIcon() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "10");
    svg.setAttribute("height", "10");
    svg.setAttribute("viewBox", "0 0 12 12");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M2.5 6.2L5 8.7L9.5 3.5");
    svg.appendChild(path);
    return svg;
  }

  function setPipelineStage(stageIdx, stepLabels) {
    // stageIdx: -1 reset, 0..3 running, 4 all done
    const pct = stageIdx < 0 ? 0 : stageIdx >= 4 ? 100 : (stageIdx + 1) * 25;
    pipelineProgressFill.style.width = `${pct}%`;

    stepEls.forEach((el, idx) => {
      const marker = el.querySelector(".step-marker");
      const textEl = el.querySelector(".step-text");
      if (stepLabels && stepLabels[idx]) {
        textEl.textContent = stepLabels[idx];
      }
      el.classList.remove("active", "done");
      marker.innerHTML = "";
      if (stageIdx > idx) {
        el.classList.add("done");
        marker.appendChild(createSvgCheckIcon());
      } else if (stageIdx === idx) {
        el.classList.add("active");
      }
    });
  }

  function renderTable(headCols, rows) {
    ragTableHead.innerHTML = "";
    ragTableBody.innerHTML = "";

    const trHead = document.createElement("tr");
    headCols.forEach((col, i) => {
      const th = document.createElement("th");
      th.textContent = col;
      if (i === headCols.length - 1 && col.toLowerCase().includes("chunk")) {
        th.style.textAlign = "right";
      }
      trHead.appendChild(th);
    });
    ragTableHead.appendChild(trHead);

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      row.forEach((cell, i) => {
        const td = document.createElement("td");
        td.textContent = String(cell);
        if (i === 0 || /^\d/.test(String(cell))) {
          td.classList.add("mono");
        }
        tr.appendChild(td);
      });
      ragTableBody.appendChild(tr);
    });
  }

  function selectInspectorNode(node) {
    Array.from(svgNodesLayer.querySelectorAll(".graph-node-group")).forEach((g) => {
      g.classList.toggle("selected", g.getAttribute("data-id") === node.id);
    });
    inspectorLabel.textContent = `:${node.type} (${node.label})`;
    inspectorProps.textContent = JSON.stringify(node.props, null, 0);
  }

  function clipLineToBox(cx, cy, tx, ty, halfW, halfH) {
    const dx = tx - cx;
    const dy = ty - cy;
    if (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001) return { x: cx, y: cy };
    const sx = Math.abs(dx) > 0.001 ? halfW / Math.abs(dx) : Infinity;
    const sy = Math.abs(dy) > 0.001 ? halfH / Math.abs(dy) : Infinity;
    const t = Math.min(sx, sy);
    return { x: cx + dx * t, y: cy + dy * t };
  }

  function renderKnowledgeGraph(scenario) {
    svgEdgesLayer.innerHTML = "";
    svgNodesLayer.innerHTML = "";

    const nodeWidth = 122;
    const nodeHeight = 46;
    const nodeMap = new Map();
    scenario.nodes.forEach((n) => nodeMap.set(n.id, n));

    const labelGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");

    scenario.edges.forEach((edge, idx) => {
      const src = nodeMap.get(edge.from);
      const dst = nodeMap.get(edge.to);
      if (!src || !dst) return;

      const x1 = src.x + nodeWidth / 2;
      const y1 = src.y + nodeHeight / 2;
      const x2 = dst.x + nodeWidth / 2;
      const y2 = dst.y + nodeHeight / 2;

      const p1 = clipLineToBox(x1, y1, x2, y2, nodeWidth / 2 + 2, nodeHeight / 2 + 2);
      const p2 = clipLineToBox(x2, y2, x1, y1, nodeWidth / 2 + 5, nodeHeight / 2 + 5);
      const startX = p1.x;
      const startY = p1.y;
      const endX = p2.x;
      const endY = p2.y;

      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", startX.toFixed(1));
      line.setAttribute("y1", startY.toFixed(1));
      line.setAttribute("x2", endX.toFixed(1));
      line.setAttribute("y2", endY.toFixed(1));
      line.setAttribute("class", `graph-edge-line${edge.isolated ? " isolated" : ""}`);
      line.setAttribute("marker-end", edge.isolated ? "url(#edgeArrowGreen)" : "url(#edgeArrow)");

      const len = Math.ceil(Math.hypot(endX - startX, endY - startY));
      if (!edge.isolated) {
        line.style.strokeDasharray = String(len);
        line.style.strokeDashoffset = String(len);
        schedule(() => {
          line.style.strokeDashoffset = "0";
        }, 60 + idx * 90);
      }

      const tPos = edge.labelT || 0.5;
      const lx = startX + (endX - startX) * tPos;
      const ly = startY + (endY - startY) * tPos;
      const labelW = edge.rel.length * 6.0 + 12;

      const labelBox = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      labelBox.setAttribute("x", (lx - labelW / 2).toFixed(1));
      labelBox.setAttribute("y", (ly - 8).toFixed(1));
      labelBox.setAttribute("width", labelW.toFixed(1));
      labelBox.setAttribute("height", "14");
      labelBox.setAttribute("rx", "2");
      labelBox.setAttribute("fill", "#0f172a");
      labelBox.setAttribute("stroke", "#1e293b");
      labelBox.setAttribute("stroke-width", "0.8");

      const labelText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      labelText.setAttribute("x", lx.toFixed(1));
      labelText.setAttribute("y", (ly + 2.5).toFixed(1));
      labelText.setAttribute("class", "graph-edge-label");
      labelText.textContent = edge.rel;

      svgEdgesLayer.appendChild(line);
      labelGroup.appendChild(labelBox);
      labelGroup.appendChild(labelText);
    });

    svgEdgesLayer.appendChild(labelGroup);

    scenario.nodes.forEach((node) => {
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("class", `graph-node-group${node.highlight ? " highlight" : ""}${node.private ? " private" : ""}`);
      g.setAttribute("data-id", node.id);
      g.setAttribute("transform", `translate(${node.x}, ${node.y})`);

      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("width", String(nodeWidth));
      rect.setAttribute("height", String(nodeHeight));
      rect.setAttribute("rx", "3");
      rect.setAttribute("class", "graph-node-rect");

      const typeText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      typeText.setAttribute("x", "9");
      typeText.setAttribute("y", "16");
      typeText.setAttribute("class", "graph-node-type");
      typeText.textContent = `:${node.type}`;

      const lblText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      lblText.setAttribute("x", "9");
      lblText.setAttribute("y", "33");
      lblText.setAttribute("class", "graph-node-label");
      lblText.textContent = node.label;

      g.appendChild(rect);
      g.appendChild(typeText);
      g.appendChild(lblText);
      g.addEventListener("click", () => selectInspectorNode(node));
      svgNodesLayer.appendChild(g);
    });

    if (scenario.nodes.length) {
      selectInspectorNode(scenario.nodes[0]);
    }
  }

  function renderScenarioOutput(scenario) {
    ragOutputCard.classList.add("transitioning");
    schedule(() => {
      pipelineLatency.textContent = scenario.latency;
      graphBadgeText.textContent = scenario.graphBadge;
      ragGraphPath.textContent = scenario.graphPath;
      ragBadge.textContent = scenario.badgeText;
      ragSummaryText.textContent = scenario.summary;
      renderTable(scenario.tableHead, scenario.tableRows);
      ragSourcesText.textContent = scenario.sourcesText;
      ragCaveatText.textContent = scenario.caveatText;
      renderKnowledgeGraph(scenario);
      ragOutputCard.classList.remove("transitioning");
    }, 150);
  }

  function runChoreography(scenario, opts) {
    const options = opts || {};
    clearTimers();

    scenarioBtns.forEach((b) => {
      b.classList.toggle("active", Number(b.dataset.scenario) === scenario.id);
    });

    const targetText = scenario.question;
    setPipelineStage(-1, scenario.steps);

    const instant = Boolean(options.instant) || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (instant) {
      searchInput.value = targetText;
      setPipelineStage(4, scenario.steps);
      renderScenarioOutput(scenario);
      return;
    }

    searchInput.value = "";
    let charIdx = 0;
    const typeSpeed = options.fastType ? 14 : 26;

    function typeNext() {
      if (charIdx < targetText.length) {
        charIdx += 1;
        searchInput.value = targetText.slice(0, charIdx);
        schedule(typeNext, typeSpeed);
      } else {
        // Run 4 pipeline steps cleanly
        const stepDelay = options.fastType ? 160 : 280;
        [0, 1, 2, 3].forEach((step) => {
          schedule(() => setPipelineStage(step, scenario.steps), step * stepDelay + 120);
        });
        schedule(() => {
          setPipelineStage(4, scenario.steps);
          renderScenarioOutput(scenario);
          if (isAutoLooping) {
            schedule(() => {
              activeScenarioIdx = (activeScenarioIdx + 1) % SCENARIOS.length;
              runChoreography(SCENARIOS[activeScenarioIdx]);
            }, 4600);
          }
        }, 4 * stepDelay + 180);
      }
    }

    typeNext();
  }

  async function runLiveOrPreviewQuery(rawQuestion) {
    const q = (rawQuestion || "").trim();
    if (!q) return;

    isAutoLooping = false;
    updateLoopUi();

    if (EXTRA_PROMPTS[q]) {
      runChoreography(EXTRA_PROMPTS[q], { fastType: true });
      return;
    }

    clearTimers();
    searchInput.value = q;
    const steps = [
      "Parsing query entities & fiscal scope",
      "Traversing Neo4j Aura knowledge graph",
      "Ranking BGE vectors + lexical terms",
      "Formatting verified page citations"
    ];
    setPipelineStage(0, steps);

    // Optional live backend check if running behind Bharat Praman FastAPI
    const canTryApi = window.location.protocol.startsWith("http") && (window.location.port === "8000" || window.location.hostname.includes("railway.app"));
    if (canTryApi) {
      try {
        setPipelineStage(1, steps);
        const resp = await fetch("/api/rag/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: q, ministry: "all", detail_level: "short" })
        });
        if (resp.ok) {
          const data = await resp.json();
          const hits = data.hits || [];
          if (hits.length) {
            setPipelineStage(4, steps);
            const dynamicScenario = {
              id: -1,
              question: q,
              latency: "Live Aura Hybrid Search",
              graphBadge: "Live /api/rag/search",
              graphPath: `Aura Hybrid -> ${hits[0].ministry || "Union"} -> ${hits[0].file || "Document"} (p.${hits[0].page || 1})`,
              badgeText: "Live Corpus Match",
              steps: steps,
              summary: hits[0].excerpt ? hits[0].excerpt.slice(0, 290) + "..." : "Retrieved live excerpts from Neo4j Aura.",
              tableHead: ["Document", "Ministry", "FY", "Page"],
              tableRows: hits.slice(0, 3).map((h) => [
                h.file || h.title || "Report",
                h.ministry || "Union",
                h.year || "-",
                `p. ${h.page || 1}`
              ]),
              sourcesText: `Retrieved ${hits.length} primary passages via Neo4j BGE + Fulltext RRF`,
              caveatText: data.glossary_note ? `Acronyms expanded: ${data.glossary_note}` : "Live read-only search response",
              nodes: SCENARIOS[0].nodes,
              edges: SCENARIOS[0].edges
            };
            renderScenarioOutput(dynamicScenario);
            return;
          }
        }
      } catch (_) {
        // Cleanly fall back to deterministic preview trace
      }
    }

    // Fallback keyword match across showcase scenarios
    const lower = q.toLowerCase();
    let matched = SCENARIOS[0];
    if (lower.includes("shri") || lower.includes("edu") || lower.includes("school")) matched = SCENARIOS[1];
    else if (lower.includes("private") || lower.includes("dpr") || lower.includes("brief") || lower.includes("tenant")) matched = SCENARIOS[2];
    else if (lower.includes("defen") || lower.includes("home") || lower.includes("capex")) matched = SCENARIOS[3];

    const customTrace = { ...matched, id: -1, question: q };
    [1, 2, 3].forEach((s) => schedule(() => setPipelineStage(s, steps), s * 160));
    schedule(() => {
      setPipelineStage(4, steps);
      renderScenarioOutput(customTrace);
    }, 640);
  }

  // Hero Controls
  scenarioBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.dataset.scenario);
      isAutoLooping = false;
      updateLoopUi();
      activeScenarioIdx = idx;
      runChoreography(SCENARIOS[idx], { fastType: true });
    });
  });

  chipBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = btn.dataset.prompt;
      runLiveOrPreviewQuery(prompt);
    });
  });

  heroQueryForm.addEventListener("submit", (e) => {
    e.preventDefault();
    runLiveOrPreviewQuery(searchInput.value);
  });

  searchInput.addEventListener("focus", () => {
    if (isAutoLooping) {
      isAutoLooping = false;
      clearTimers();
      updateLoopUi();
    }
  });

  loopToggleBtn.addEventListener("click", () => {
    isAutoLooping = !isAutoLooping;
    updateLoopUi();
    if (isAutoLooping) {
      activeScenarioIdx = (activeScenarioIdx + 1) % SCENARIOS.length;
      runChoreography(SCENARIOS[activeScenarioIdx]);
    } else {
      clearTimers();
      setPipelineStage(4, SCENARIOS[activeScenarioIdx].steps);
      renderScenarioOutput(SCENARIOS[activeScenarioIdx]);
    }
  });

  // Control Plane Tabs
  const tabBtns = Array.from(document.querySelectorAll(".tab-btn"));
  const tabPanels = Array.from(document.querySelectorAll(".control-panel"));
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      tabBtns.forEach((b) => b.classList.toggle("active", b === btn));
      tabPanels.forEach((p) => p.classList.toggle("active", p.id === `panel-${target}`));
    });
  });

  // Interactive Chunking + Tenancy Preview State
  const chunkState = { tokens: "512", rules: "strict", model: "bge-small" };
  const tenancyState = { scope: "hybrid", clearance: "internal" };

  const chunkPreviewMeta = document.getElementById("chunkPreviewMeta");
  const chunkPreviewCode = document.getElementById("chunkPreviewCode");
  const cypherPreviewMeta = document.getElementById("cypherPreviewMeta");
  const cypherPreviewCode = document.getElementById("cypherPreviewCode");

  const MODEL_SPECS = {
    "bge-small": { name: "BAAI/bge-small-en-v1.5", dim: "384-dim", index: "bge_chunk_embeddings", speed: "~20ms CPU query" },
    "bge-m3": { name: "BAAI/bge-m3 (EN + Hindi)", dim: "1024-dim", index: "bge_m3_chunk_embeddings", speed: "Bilingual dense+sparse" },
    "qwen3": { name: "Qwen/Qwen3-Embedding-0.6B", dim: "1024-dim", index: "qwen_chunk_embeddings", speed: "Instruction-aware retrieval" }
  };

  function updateChunkPreview() {
    const spec = MODEL_SPECS[chunkState.model];
    chunkPreviewMeta.textContent = `MODEL: ${spec.name} · ${spec.dim} · ${spec.speed}`;
    const prefix = chunkState.rules === "strict"
      ? `[Chapter IV | Rural Roads (PMGSY) | Unit: Rs. in Crore]\nTable 4.2: Expenditure Summary (Footnote * bound)`
      : `Raw sliding window split (${chunkState.tokens} tokens, headers dropped)`;

    chunkPreviewCode.textContent = [
      `{`,
      `  "chunker": "${chunkState.rules === "strict" ? "gov_report_structured" : "sliding_window"}",`,
      `  "max_tokens": ${chunkState.tokens},`,
      `  "freeze_table_units": ${chunkState.rules === "strict"},`,
      `  "bind_footnotes": ${chunkState.rules === "strict"},`,
      `  "embed_model": "${spec.name}",`,
      `  "neo4j_vector_index": "${spec.index}",`,
      `  "vector_dimensions": ${parseInt(spec.dim, 10)},`,
      `  "chunk_preview": ${JSON.stringify(prefix)}`,
      `}`
    ].join("\n");
  }

  function updateTenancyPreview() {
    const isHybrid = tenancyState.scope === "hybrid";
    const clearanceLvl = tenancyState.clearance === "restricted" ? 2 : 1;
    cypherPreviewMeta.textContent = isHybrid
      ? `ISOLATED TENANT OVERLAY · CLEARANCE <= ${clearanceLvl}`
      : `PUBLIC MINISTRY SPINE ONLY · READ_ACCESS`;

    const tenantPredicate = isHybrid
      ? `WHERE d.tenant_id IN ['public', $org_id]\n  AND coalesce(d.clearance_level, 0) <= $user_clearance`
      : `WHERE d.tenant_id = 'public'\n  AND coalesce(d.clearance_level, 0) = 0`;

    cypherPreviewCode.textContent = [
      `CALL db.index.vector.queryNodes('bge_chunk_embeddings', $top_k, $q_vec)`,
      `YIELD node AS c, score`,
      `MATCH (d:Document)-[:HAS_CHUNK]->(c)`,
      tenantPredicate,
      `OPTIONAL MATCH (c)-[:MENTIONS]->(s:Scheme)`,
      `RETURN d.title AS source_doc, d.year AS fy, c.page AS page,`,
      `       c.breadcrumb AS context, collect(DISTINCT s.name) AS schemes, score`,
      `ORDER BY score DESC LIMIT 12`
    ].join("\n");
  }

  document.querySelectorAll(".seg-group").forEach((group) => {
    const key = group.dataset.control;
    group.querySelectorAll(".seg-option").forEach((opt) => {
      opt.addEventListener("click", () => {
        group.querySelectorAll(".seg-option").forEach((o) => o.classList.remove("active"));
        opt.classList.add("active");
        if (key in chunkState) {
          chunkState[key] = opt.dataset.val;
          updateChunkPreview();
        } else if (key in tenancyState) {
          tenancyState[key] = opt.dataset.val;
          updateTenancyPreview();
        }
      });
    });
  });

  // Animated Counters & Scroll Reveals
  function animateCounter(el) {
    if (el.dataset.animated) return;
    el.dataset.animated = "1";
    const target = Number(el.dataset.count || 0);
    const suffix = el.dataset.suffix || "";
    if (target === 0 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.textContent = `${target.toLocaleString("en-IN")}${suffix}`;
      return;
    }
    const duration = 900;
    const start = performance.now();
    function step(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const val = Math.round(target * eased);
      el.textContent = `${val.toLocaleString("en-IN")}${suffix}`;
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  const revealEls = document.querySelectorAll(".reveal");
  const counterEls = document.querySelectorAll(".metric-value[data-count]");
  if ("IntersectionObserver" in window) {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            entry.target.querySelectorAll(".metric-value[data-count]").forEach(animateCounter);
            if (entry.target.matches(".metric-value[data-count]")) animateCounter(entry.target);
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.14 }
    );
    revealEls.forEach((el) => obs.observe(el));
    counterEls.forEach((el) => obs.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("is-visible"));
    counterEls.forEach(animateCounter);
  }

  // Initialize
  updateChunkPreview();
  updateTenancyPreview();
  updateLoopUi();
  runChoreography(SCENARIOS[0], { instant: !isAutoLooping });
})();
