#!/usr/bin/env python3
"""Build chat-format SFT rows from verified TLAPS proof artifacts."""
from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path
from typing import Iterable

REPO = Path(__file__).resolve().parents[1]

DEVELOPER_PROMPT = (
    "You are ChatTLA, a TLA+ proof assistant. Produce complete, "
    "TLAPS-checkable TLA+ modules and proofs only."
)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _iter_proofs_from_tar(path: Path) -> Iterable[tuple[str, str]]:
    with tarfile.open(path, "r:gz") as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.isfile()
            and "/proofs/" in member.name
            and member.name.endswith(".tla")
            and "/.tlacache/" not in member.name
        ]
        for member in sorted(members, key=lambda item: item.name):
            handle = archive.extractfile(member)
            if handle is None:
                continue
            yield Path(member.name).stem, handle.read().decode("utf-8", errors="replace")


def build_rows(artifact: Path, verifier: str) -> list[dict]:
    rows = []
    for module, proof_text in _iter_proofs_from_tar(artifact):
        rows.append(
            {
                "module": module,
                "source_artifact": _display_path(artifact),
                "verifier": verifier,
                "messages": [
                    {"role": "developer", "content": DEVELOPER_PROMPT},
                    {
                        "role": "user",
                        "content": f"Produce the complete TLAPS-checked proof module for {module}.",
                    },
                    {"role": "assistant", "channel": "final", "content": proof_text},
                ],
                "completion": proof_text,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=(
            REPO
            / "outputs"
            / "hf_publish"
            / "chattla-tla-prover-108-108"
            / "tlaps_reproduced_final_160816.tar.gz"
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO / "data" / "processed" / "tla_prover" / "verified_tlaps_sft_seed.jsonl",
    )
    parser.add_argument("--verifier", default="TLAPS 1.5.0 --threads 1")
    args = parser.parse_args()

    if not args.artifact.is_file():
        raise FileNotFoundError(f"artifact not found: {args.artifact}")

    rows = build_rows(args.artifact, args.verifier)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")

    print(
        json.dumps(
            {
                "artifact": _display_path(args.artifact),
                "out": _display_path(args.out),
                "rows": len(rows),
                "completion_chars": sum(len(row["completion"]) for row in rows),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
