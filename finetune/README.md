# Bharat Praman — Text-to-Cypher Fine-Tuning Pipeline

Fine-tunes a small open-weights model (e.g. `Qwen/Qwen2.5-Coder-3B-Instruct`) to emit
schema-bounded, parameterized, read-only Neo4j Cypher JSON matching `GEMINI_PLAN_SCHEMA`
in `main.py`.

## Step-by-step workflow

### Step 1: Export your live Neo4j schema & exact category values (Read-Only)
Runs locally using your `.env` / `BACKEND/.env` (never commits or prints secrets):
```powershell
python finetune/export_schema_snapshot.py
```
This writes `data/schema_snapshot.json` with exact `Party.name`, `State.name`,
`Election.year`, `CriminalCase.status`, and relationship directions from your live DB.

### Step 2: Build the validated training & validation datasets
```powershell
python finetune/build_dataset.py
```
This reads `data/schema_snapshot.json`, `cypher_examples.json`, `cypher_templates.py`,
plus curated `:Affidavit` and `unsupported` refusal examples, filters every query
through `main.py`'s strict validator rules, and writes:
- `data/finetune_train.jsonl`
- `data/finetune_val.jsonl`

### Step 3: Execution-verify every query against Neo4j (Read-Only)
```powershell
python finetune/verify_dataset_against_neo4j.py
```
Drops any query that throws a Neo4j error or returns 0 rows, producing:
- `data/finetune_train_verified.jsonl`
- `data/finetune_val_verified.jsonl`

### Step 4: Train QLoRA (Google Colab T4 or local NVIDIA GPU)
On a GPU machine (with `torch transformers datasets accelerate peft bitsandbytes trl`):
```bash
python finetune/train_qlora.py --model Qwen/Qwen2.5-Coder-3B-Instruct --epochs 3
```

### Step 5: Serve & evaluate
Once trained, you can merge the LoRA adapter to GGUF (for Ollama / `llama.cpp`) or serve
it with vLLM behind an OpenAI-compatible endpoint, and run an exact-execution evaluation
on `data/finetune_val_verified.jsonl` before swapping it into `main.py`.
