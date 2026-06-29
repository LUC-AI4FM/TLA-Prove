#!/usr/bin/env python3
"""Disabled legacy uploader kept only as a pointer to the guarded publish path."""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "scripts/upload_v11.py is disabled. "
        "Use `python -m src.training.publish_hf --dry-run` to inspect blockers "
        "and `python -m src.training.publish_hf` for the guarded publish path.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
