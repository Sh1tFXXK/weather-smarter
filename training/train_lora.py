from __future__ import annotations

import argparse
import os
from typing import Dict, List

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
    default_data_collator,
)


def build_prompt(instruction: str, user_input: str) -> str:
    if user_input:
        return (
            "### Instruction:\n"
            f"{instruction}\n\n"
            "### Input:\n"
            f"{user_input}\n\n"
            "### Response:\n"
        )
    return (
        "### Instruction:\n"
        f"{instruction}\n\n"
        "### Response:\n"
    )


def make_dataset(path: str, tokenizer, max_length: int):
    dataset = load_dataset("json", data_files=path, split="train")

    def tokenize(example: Dict[str, str]) -> Dict[str, List[int]]:
        instruction = (example.get("instruction") or "").strip()
        user_input = (example.get("input") or "").strip()
        output = (example.get("output") or "").strip()

        prompt = build_prompt(instruction, user_input)
        full_text = prompt + output

        tokenized = tokenizer(
            full_text,
            truncation=True,
            max_length=max_length,
        )
        prompt_ids = tokenizer(
            prompt,
            truncation=True,
            max_length=max_length,
        )["input_ids"]

        labels = tokenized["input_ids"].copy()
        prompt_len = min(len(labels), len(prompt_ids))
        labels[:prompt_len] = [-100] * prompt_len
        tokenized["labels"] = labels
        return tokenized

    return dataset.map(tokenize, remove_columns=dataset.column_names)


def main() -> None:
    parser = argparse.ArgumentParser(description="LoRA fine-tuning (QLoRA)")
    parser.add_argument("--model", required=True, help="Base model name or path")
    parser.add_argument("--data", required=True, help="JSONL training file")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument(
        "--target-modules",
        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
    )
    parser.add_argument("--bf16", action="store_true")
    args = parser.parse_args()

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16 if args.bf16 else torch.float16,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)

    target_modules = [m.strip() for m in args.target_modules.split(",") if m.strip()]
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )
    model = get_peft_model(model, lora_config)

    dataset = make_dataset(args.data, tokenizer, args.max_length)

    os.makedirs(args.output, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=args.output,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        logging_steps=20,
        save_strategy="epoch",
        fp16=not args.bf16,
        bf16=args.bf16,
        optim="paged_adamw_8bit",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=default_data_collator,
    )
    trainer.train()

    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)


if __name__ == "__main__":
    main()
