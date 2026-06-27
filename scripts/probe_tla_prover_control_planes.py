#!/usr/bin/env python3
"""Probe candidate control-plane hosts for the TLA prover handoff."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_control_plane_probe.json"


@dataclass(frozen=True)
class Candidate:
    name: str
    host: str
    command: str = "hostname"


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def default_candidates() -> list[Candidate]:
    candidates = []
    for name, env_name in [
        ("relay", "CHATTLA_RELAY_HOST"),
        ("mac", "CHATTLA_MAC_HOST"),
        ("sophia_direct", "SOPHIA_HOST"),
        ("polaris", "CHATTLA_POLARIS_HOST"),
        ("aisec", "CHATTLA_AISEC_HOST"),
    ]:
        host = os.environ.get(env_name)
        if host:
            candidates.append(Candidate(name, host))
    return candidates


def parse_candidate(text: str) -> Candidate:
    parts = text.split(":", 2)
    if len(parts) == 2:
        name, host = parts
        command = "hostname"
    elif len(parts) == 3:
        name, host, command = parts
    else:
        raise ValueError(f"candidate must be name:host[:command], got {text!r}")
    return Candidate(name=name, host=host, command=command)


def _default_runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=12)


def _command(candidate: Candidate) -> list[str]:
    if candidate.host == "true":
        return ["true"]
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        candidate.host,
        candidate.command,
    ]


def probe_candidates(candidates: list[Candidate], *, runner: Runner = _default_runner) -> dict:
    rows = []
    for candidate in candidates:
        cmd = _command(candidate)
        try:
            result = runner(cmd)
            returncode = result.returncode
            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
        except Exception as exc:  # pragma: no cover - defensive live path
            returncode = 124
            stdout = ""
            stderr = str(exc)
        rows.append(
            {
                "name": candidate.name,
                "host": candidate.host,
                "command": candidate.command,
                "reachable": returncode == 0,
                "returncode": returncode,
                "stdout": stdout[-2000:],
                "stderr": stderr[-2000:],
            }
        )
    best = next((row for row in rows if row["reachable"]), None)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": best is not None,
        "best_candidate": best,
        "candidates": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="append", help="Candidate as name:host[:command]")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    candidates = [parse_candidate(item) for item in args.candidate] if args.candidate else default_candidates()
    if not candidates:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ok": False,
            "best_candidate": None,
            "candidates": [],
            "error": "No candidates configured. Set CHATTLA_RELAY_HOST, SOPHIA_HOST, CHATTLA_POLARIS_HOST, CHATTLA_AISEC_HOST, or pass --candidate.",
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    payload = probe_candidates(candidates)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
