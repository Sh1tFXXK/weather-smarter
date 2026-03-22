import json
from pathlib import Path


SESSION = Path(r"C:\Users\Administrator\.codex\sessions\2026\03\15\rollout-2026-03-15T23-12-16-019cf20e-1ba4-7212-838b-c09221ddc82b.jsonl")


def main() -> None:
    out = Path("scripts/frontend_patches_dump.txt")
    chunks: list[str] = []
    count = 0
    for line in SESSION.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = obj.get("payload", {})
        if payload.get("type") != "custom_tool_call" or payload.get("name") != "apply_patch":
            continue
        patch = payload.get("input", "")
        if "frontend/index.html" not in patch and "frontend\\index.html" not in patch:
            continue
        count += 1
        chunks.append(f"PATCH {count} {obj.get('timestamp', '')}\n{patch}\n\n===END_PATCH===\n")
    chunks.append(f"TOTAL {count}\n")
    out.write_text("".join(chunks), encoding="utf-8")


if __name__ == "__main__":
    main()
