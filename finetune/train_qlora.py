"""QLoRA fine-tuning script for Bharat Praman Text-to-Cypher (Colab T4 or local GPU).

Trains a small instruction model (default: Qwen/Qwen2.5-Coder-3B-Instruct) on
data/finetune_train_verified.jsonl (falls back to data/finetune_train.jsonl) to
emit strict JSON plans matching main.py's GEMINI_PLAN_SCHEMA.

Install training deps in your GPU environment / Colab:
    pip install torch transformers datasets accelerate peft bitsandbytes trl

Usage:
    python finetune/train_qlora.py --epochs 3 --batch-size 2 --grad-accum 8
"""

import argparse
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--max-seq-len", type=int, default=2048)
    parser.add_argument("--output-dir", default=str(BASE_DIR / "models" / "bharat-praman-cypher-lora"))
    args = parser.parse_args()

    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    train_path = BASE_DIR / "data" / "finetune_train_verified.jsonl"
    if not train_path.exists():
        train_path = BASE_DIR / "data" / "finetune_train.jsonl"
    val_path = BASE_DIR / "data" / "finetune_val_verified.jsonl"
    if not val_path.exists():
        val_path = BASE_DIR / "data" / "finetune_val.jsonl"

    train_rows = load_jsonl(train_path)
    val_rows = load_jsonl(val_path)
    print(f"Using train={train_path} ({len(train_rows)} rows), val={val_path} ({len(val_rows)} rows)")

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def format_row(row):
        return {"text": tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)}

    train_ds = Dataset.from_list(train_rows).map(format_row)
    val_ds = Dataset.from_list(val_rows).map(format_row)

    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb_config,
        torch_dtype=compute_dtype,
        device_map="auto",
    )

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )

    sft_config = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=10,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        fp16=False,
        bf16=torch.cuda.is_bf16_supported(),
        max_length=args.max_seq_len,
        dataset_text_field="text",
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        peft_config=lora_config,
        args=sft_config,
    )
    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"Saved LoRA adapter & tokenizer to {args.output_dir}")


if __name__ == "__main__":
    main()
