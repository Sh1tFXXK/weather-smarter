from pathlib import Path
import sys


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit("usage: print_file_range.py <path> <start> <end>")

    path = Path(sys.argv[1])
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    lines = path.read_text(encoding="utf-8").splitlines()
    for i in range(start - 1, min(len(lines), end)):
        print(f"{i + 1}: {lines[i]}")


if __name__ == "__main__":
    main()
