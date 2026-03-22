# Fine-tuning (LoRA / QLoRA)

This project supports lightweight LoRA fine-tuning for small models (1B-4B).

## 1. Install training dependencies
```
pip install -r requirements-train.txt
```

Note: QLoRA depends on CUDA-enabled bitsandbytes. If you are on Windows,
consider using WSL2 + CUDA or train on a Linux machine.

## 2. Prepare data (JSONL)
Each line:
```json
{"instruction": "Decide if it is suitable for running", "input": "Tomorrow in Beijing", "output": "Based on the weather, running is OK ..."}
```

## 3. Run training
Example with a small base model:
```
py training/train_lora.py ^
  --model Qwen/Qwen2.5-1.5B-Instruct ^
  --data data/train.jsonl ^
  --output outputs/lora-qwen2.5-1.5b ^
  --max-length 1024 ^
  --batch-size 1 ^
  --grad-accum 8 ^
  --epochs 3
```

## 4. Use LoRA in local inference
### (Optional) Merge LoRA into base (HF)
If you need a single merged model:
```
py training/merge_lora.py ^
  --base-model Qwen/Qwen3-0.6B ^
  --adapter outputs/lora-qwen3-0.6b ^
  --output outputs/merged-qwen3-0.6b
```

### Option A: llama.cpp (GGUF)
1. Convert the LoRA adapter to GGUF using llama.cpp tooling.
2. Set environment variables:
```
setx LLM_PROVIDER llama_cpp
setx LLM_MODEL_PATH "E:\models\base.gguf"
setx LLM_LORA_PATH "E:\models\adapter.gguf"
```

### Option B: Ollama
Create a `Modelfile`:
```
FROM /path/to/base-model.gguf
ADAPTER /path/to/adapter.gguf
```

Then:
```
ollama create env-agent -f Modelfile
```
