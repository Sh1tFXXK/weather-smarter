from pathlib import Path
import sys


def main() -> None:
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    lines = Path("frontend/index.html").read_text(encoding="utf-8").splitlines()
    for i in range(start - 1, min(len(lines), end)):
        print(f"{i + 1}: {lines[i]}")


if __name__ == "__main__":
    main()
