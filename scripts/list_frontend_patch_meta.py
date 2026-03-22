import json
from pathlib import Path


SESSION = Path(r"C:\Users\Administrator\.codex\sessions\2026\03\18\rollout-2026-03-18T21-37-58-019d012a-da19-7d50-9823-9bb83562ec06.jsonl")


def main() -> None:
    lines = []
    for i, line in enumerate(SESSION.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = obj.get("payload", {})
        if payload.get("type") == "message" and obj.get("type") == "response_item":
            role = payload.get("role")
            if role == "user":
                text = "".join(part.get("text", "") for part in payload.get("content", []) if part.get("type") == "input_text")
                if any(key in text for key in ["精简压缩", "真正的瘦身版", "彻底干净的最终版"]):
                    lines.append(f"USER {i} {obj.get('timestamp')} {text[:120]}\n")
        if payload.get("type") == "custom_tool_call" and payload.get("name") == "apply_patch":
            patch = payload.get("input", "")
            if "frontend/index.html" in patch or "frontend\\index.html" in patch:
                head = patch.splitlines()[:8]
                lines.append(f"PATCH {i} {obj.get('timestamp')}\n")
                for item in head:
                    lines.append(item + "\n")
                lines.append("---\n")
    Path("scripts/frontend_patch_meta.txt").write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
