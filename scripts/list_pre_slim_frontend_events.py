import json
from pathlib import Path


SESSION = Path(r"C:\Users\Administrator\.codex\sessions\2026\03\18\rollout-2026-03-18T21-37-58-019d012a-da19-7d50-9823-9bb83562ec06.jsonl")


def main() -> None:
    root = Path(__file__).resolve().parent
    out = []
    hit_user = False
    for i, line in enumerate(SESSION.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = obj.get("payload", {})
        if payload.get("type") == "message" and obj.get("type") == "response_item" and payload.get("role") == "user":
            text = "".join(part.get("text", "") for part in payload.get("content", []) if part.get("type") == "input_text")
            if "精简压缩" in text:
                out.append(f"USER {i} {obj.get('timestamp')} {text}\n")
                hit_user = True
                break
        if payload.get("type") == "custom_tool_call" and payload.get("name") == "apply_patch":
            patch = payload.get("input", "")
            if "frontend/index.html" in patch or "frontend\\index.html" in patch:
                head = "\n".join(patch.splitlines()[:14])
                out.append(f"PATCH {i} {obj.get('timestamp')}\n{head}\n---\n")
    (root / "pre_slim_frontend_events.txt").write_text("".join(out[-80:]), encoding="utf-8")


if __name__ == "__main__":
    main()
