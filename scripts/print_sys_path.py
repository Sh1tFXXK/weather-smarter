from pathlib import Path
from pprint import pprint

import sys

if __name__ == "__main__":
    pprint(sys.path[:8])
    pprint(Path.cwd())
