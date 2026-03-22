from pathlib import Path


def main() -> None:
    text = Path("frontend/index.html").read_text(encoding="utf-8")
    lines = text.splitlines()
    keys = [
        "dashboard-shell",
        "dashboard-main",
        "dashboard-side",
        "side-panel",
        "Advanced Console",
        "编队模式",
        "squad-row",
        "action-deck",
        "action-chip",
        "wallQuickAction",
        "wallQuickRunBtn",
        "wallVoiceStartBtn",
        "story-pane",
        "ops-pane",
        "ops-shell",
        "story-hidden",
    ]
    for key in keys:
        print(f"{key}: {key in text}")

    start = text.find("<body>")
    script = text.find("<script>")
    print("\n=== BODY HTML START ===\n")
    print(text[start:script][:20000])

    ranges = [
        (840, 890),
        (1358, 1468),
        (1620, 1695),
        (1696, 1805),
        (1580, 2025),
        (2888, 3055),
        (3208, 3240),
        (3440, 3470),
    ]
    for start_line, end_line in ranges:
        print(f"\n=== RANGE {start_line}-{end_line} ===\n")
        for i in range(start_line - 1, min(len(lines), end_line)):
            print(f"{i + 1}: {lines[i]}")


if __name__ == "__main__":
    main()
