"""Creates data/lanes.csv, carriers.csv, offers.csv and baseline.csv (fixed seed, always the same)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from allocator.synthetic import generate  # noqa: E402

if __name__ == "__main__":
    print(generate(ROOT / "data"))
