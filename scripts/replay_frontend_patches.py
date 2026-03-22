from __future__ import annotations

from pathlib import Path


DUMP = Path("scripts/frontend_patches_dump.txt")
TARGET = Path("frontend/index.html")


def strip_added_prefix(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("+"):
            lines.append(line[1:])
    return "\n".join(lines) + "\n"


def parse_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    in_patch = False
    for line in text.splitlines():
        if line.startswith("*** Begin Patch"):
            in_patch = True
            current = [line]
            continue
        if in_patch:
            current.append(line)
            if line.startswith("*** End Patch"):
                blocks.append("\n".join(current) + "\n")
                in_patch = False
                current = []
    return blocks


def apply_update(content: str, lines: list[str]) -> str:
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("@@"):
            i += 1
            continue
        i += 1
        old_lines: list[str] = []
        new_lines: list[str] = []
        while i < len(lines) and not lines[i].startswith("@@"):
            ln = lines[i]
            if ln.startswith("*** End"):
                break
            if ln.startswith(" "):
                old_lines.append(ln[1:])
                new_lines.append(ln[1:])
            elif ln.startswith("-"):
                old_lines.append(ln[1:])
            elif ln.startswith("+"):
                new_lines.append(ln[1:])
            i += 1
        old = "\n".join(old_lines)
        new = "\n".join(new_lines)
        if old and old not in content:
            raise RuntimeError(f"Failed to locate patch context starting with: {old_lines[:3]}")
        content = content.replace(old, new, 1)
    return content


def apply_block(content: str, block: str) -> str:
    lines = block.splitlines()
    if any(line.startswith("*** Add File:") for line in lines):
        return strip_added_prefix(block)
    if any(line.startswith("*** Delete File:") for line in lines):
        return ""
    if any(line.startswith("*** Update File:") for line in lines):
        return apply_update(content, lines)
    return content


def main() -> None:
    content = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    blocks = parse_blocks(DUMP.read_text(encoding="utf-8"))
    if blocks:
        for block in blocks:
            if "*** Add File:" in block:
                content = apply_block("", block)
                break
    for idx, block in enumerate(blocks, start=1):
        if "*** Delete File:" in block or "*** Add File:" in block:
            continue
        content = apply_block(content, block)
    TARGET.write_text(content, encoding="utf-8")
    print(f"replayed {len(blocks)} patches to {TARGET}")


if __name__ == "__main__":
    main()
