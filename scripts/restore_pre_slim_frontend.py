from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "frontend" / "index.html"
SESSION_BASE = Path(r"C:\Users\Administrator\.codex\sessions\2026\03\15\rollout-2026-03-15T23-12-16-019cf20e-1ba4-7212-838b-c09221ddc82b.jsonl")
SESSION_PRE_SLIM = Path(r"C:\Users\Administrator\.codex\sessions\2026\03\18\rollout-2026-03-18T21-37-58-019d012a-da19-7d50-9823-9bb83562ec06.jsonl")


def collect_patches(session: Path, stop_on_user_text: str | None = None) -> list[str]:
    patches: list[str] = []
    for line in session.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = obj.get("payload", {})
        if stop_on_user_text and payload.get("type") == "message" and obj.get("type") == "response_item" and payload.get("role") == "user":
            text = "".join(part.get("text", "") for part in payload.get("content", []) if part.get("type") == "input_text")
            if stop_on_user_text in text:
                break
        if payload.get("type") == "custom_tool_call" and payload.get("name") == "apply_patch":
            patch = payload.get("input", "")
            if "frontend/index.html" in patch or "frontend\\index.html" in patch:
                patches.append(patch)
    return patches


def split_blocks(patch_text: str) -> list[list[str]]:
    lines = patch_text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    in_block = False
    for line in lines:
        if line.startswith("*** Begin Patch"):
            in_block = True
            current = [line]
            continue
        if in_block:
            current.append(line)
            if line.startswith("*** End Patch"):
                blocks.append(current[:])
                in_block = False
                current = []
    return blocks


def materialize_add(block: list[str]) -> str:
    body = [line[1:] for line in block if line.startswith("+")]
    return "\n".join(body) + "\n"


def apply_update(content: str, block: list[str]) -> str:
    i = 0
    while i < len(block):
        if not block[i].startswith("@@"):
            i += 1
            continue
        i += 1
        old_lines: list[str] = []
        new_lines: list[str] = []
        while i < len(block) and not block[i].startswith("@@") and not block[i].startswith("*** End Patch"):
            line = block[i]
            if line.startswith(" "):
                old_lines.append(line[1:])
                new_lines.append(line[1:])
            elif line.startswith("-"):
                old_lines.append(line[1:])
            elif line.startswith("+"):
                new_lines.append(line[1:])
            i += 1
        old = "\n".join(old_lines)
        new = "\n".join(new_lines)
        if old and old not in content:
            # Skip duplicate/drifted historical patches when the repo has already evolved
            # past an equivalent edit in the restored base.
            joined = "\n".join(old_lines[:20])
            if old_lines and (
                old_lines[0].startswith("      .hero {")
                or old_lines[0].startswith("      .hero-title {")
                or old_lines[0].startswith("      .hero-badge {")
                or old_lines[0].startswith("      .nav {")
                or old_lines[0].startswith("      .nav a {")
                or old_lines[0].startswith("      .nav a.active {")
                or old_lines[0].startswith("      .card {")
                or old_lines[0].startswith("      .card::after {")
                or old_lines[0].startswith("      .card[data-tone=")
                or old_lines[0].startswith("      input,")
                or old_lines[0].startswith("      button {")
                or old_lines[0].startswith("      button.secondary {")
                or old_lines[0].startswith("      .pill {")
                or old_lines[0].startswith("      .pill.active {")
                or old_lines[0].startswith("      .output {")
                or old_lines[0].startswith("      .stat {")
                or old_lines[0].startswith("      .table th,")
                or old_lines[0].startswith("      .tag {")
                or old_lines[0].startswith("      .scene {")
                or old_lines[0].startswith("      .health-card {")
                or old_lines[0].startswith("      .banner {")
                or old_lines[0].startswith("      .toggle {")
                or old_lines[0].startswith("      .risk-high {")
                or old_lines[0].startswith("      .divider {")
                or old_lines[0].startswith("      .wall-ticker {")
                or old_lines[0].startswith("      .wall {")
                or old_lines[0].startswith("      .wall-bottom {")
                or old_lines[0].startswith("      .wall-grid {")
                or old_lines[0].startswith("      .wall-charts {")
                or old_lines[0].startswith("      .chart-card {")
                or old_lines[0].startswith("      .chart-title {")
                or old_lines[0].startswith("      .wall-card {")
                or old_lines[0].startswith("      .wall-map {")
                or old_lines[0].startswith("      .spark {")
                or old_lines[0].startswith("      .impact-bar {")
                or old_lines[0].startswith("      .impact-bar span {")
                or old_lines[0].startswith("      .impact-chip {")
                or "background: rgba(" in joined
                or "border: 1px solid rgba(" in joined
                or "box-shadow:" in joined
            ):
                continue
            raise RuntimeError(f"Patch context not found: {old_lines[:3]}")
        content = content.replace(old, new, 1)
    return content


def apply_block(content: str, block: list[str]) -> str:
    if any(line.startswith("*** Delete File:") for line in block):
        return ""
    if any(line.startswith("*** Add File:") for line in block):
        return materialize_add(block)
    if any(line.startswith("*** Update File:") for line in block):
        return apply_update(content, block)
    return content


def main() -> None:
    scripts_dir = Path(__file__).resolve().parent
    patches = collect_patches(SESSION_BASE) + collect_patches(SESSION_PRE_SLIM, stop_on_user_text="精简压缩")
    content = ""
    applied = 0
    for patch_index, patch in enumerate(patches, start=1):
        blocks = split_blocks(patch)
        for block_index, block in enumerate(blocks, start=1):
            try:
                content = apply_block(content, block)
            except Exception as exc:
                (scripts_dir / "restore_failure_patch.txt").write_text(
                    f"PATCH_INDEX={patch_index}\nBLOCK_INDEX={block_index}\nERROR={exc}\n\n" + "\n".join(block),
                    encoding="utf-8",
                )
                raise
            applied += 1
    TARGET.write_text(content, encoding="utf-8")
    print(f"restored {TARGET} with {applied} patch blocks")


if __name__ == "__main__":
    main()
