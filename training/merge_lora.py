from __future__ import annotations

import argparse
import os

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge LoRA adapter into base model")
    parser.add_argument("--base-model", required=True, help="Base model name or path")
    parser.add_argument("--adapter", required=True, help="LoRA adapter path")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--bf16", action="store_true")
    args = parser.parse_args()

    dtype = torch.bfloat16 if args.bf16 else torch.float16
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=dtype,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(model, args.adapter)
    model = model.merge_and_unload()

    os.makedirs(args.output, exist_ok=True)
    model.save_pretrained(args.output, safe_serialization=True)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    tokenizer.save_pretrained(args.output)


if __name__ == "__main__":
    main()
