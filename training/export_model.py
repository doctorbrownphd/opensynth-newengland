"""Export trained CVAE weights into the package for distribution.

Copies best_model.pt, config.json, and normalization.json from
training/checkpoints/ to src/opensynth_ne/weights/.
"""

from __future__ import annotations

import shutil
from pathlib import Path

CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"
WEIGHTS_DIR = Path(__file__).parent.parent / "src" / "opensynth_ne" / "weights"

REQUIRED_FILES = ["best_model.pt", "config.json", "normalization.json"]


def main():
    # Verify checkpoints exist
    for fname in REQUIRED_FILES:
        src = CHECKPOINT_DIR / fname
        if not src.exists():
            print(f"ERROR: {src} not found. Run train.py first.")
            return

    # Create weights directory
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    # Copy files
    for fname in REQUIRED_FILES:
        src = CHECKPOINT_DIR / fname
        dst = WEIGHTS_DIR / fname
        shutil.copy2(src, dst)
        size = dst.stat().st_size
        print(f"  {fname}: {size:,} bytes → {dst}")

    print(f"\nExported to {WEIGHTS_DIR}/")
    print("The CVAE will be auto-detected by generate_day() on next call.")


if __name__ == "__main__":
    main()
