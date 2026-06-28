"""overnight_cegis.py — unattended census + CEGIS invariant-search over the
FormaLLM corpus, using local TLC (src/prover) and an Ollama proposer.

For every <name>/tla/*.tla module that defines Next and TypeOK, it:
  1. runs the TLC inductiveness oracle on TypeOK (the cheap census), and
  2. if TypeOK is not immediately inductive, runs the CEGIS loop (bounded) to
     try to discover a strengthening, calling the proposer model.

Robust by construction: per-module try/except, per-module TLC timeout, a global
proposer-call cap, a wall-clock budget, and append+flush JSONL so a crash or
laptop sleep never loses prior results. Resumable: modules already in the output
are skipped.

Proposer defaults to the LOCAL gpt-oss:20b (zero marginal cost). Override with
CHATTLA_OVERNIGHT_MODEL=<model> (e.g. gpt-oss:120b-cloud) to use a cloud teacher.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.prover.inductiveness import check_inductive
from src.prover.cegis import search_inductive_invariant
from src.prover.proposer import make_invariant_proposer

OLLAMA_URL = os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
MODEL = os.getenv("CHATTLA_OVERNIGHT_MODEL", "gpt-oss:20b")

_HAS_NEXT = re.compile(r"(?m)^\s*Next\s*==")
_HAS_TYPEOK = re.compile(r"(?m)^\s*TypeOK\s*==")
_HAS_CONST = re.compile(r"(?m)^\s*CONSTANT")


def chat_fn(prompt: str) -> str:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.2},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        data = json.loads(r.read())
    return data.get("message", {}).get("content", "")


def classify_error(err: str) -> str:
    e = (err or "").lower()
    if "is not assigned" in e or "constant" in e:
        return "constant_unassigned"
    if "could not parse" in e or "was expecting" in e or "lexical" in e or "encountered" in e:
        return "parse"
    if "enumerab" in e or "too large" in e or "not finite" in e or "attempted to" in e:
        return "non_enumerable"
    if "timed out" in e or "timeout" in e:
        return "timeout"
    if "cannot find" in e or "unknown module" in e:
        return "module_missing"
    return "other"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "outputs" / "overnight_cegis" / "results.jsonl"))
    ap.add_argument("--limit", type=int, default=0, help="0 = all modules")
    ap.add_argument("--per-module-timeout", type=int, default=60)
    ap.add_argument("--max-iters", type=int, default=3)
    ap.add_argument("--max-proposer-calls", type=int, default=80)
    ap.add_argument("--time-budget-min", type=int, default=420)
    ap.add_argument("--no-proposer", action="store_true", help="census only (no model calls)")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done = set()
    if out_path.exists():
        for line in out_path.open():
            try:
                done.add(json.loads(line)["module"])
            except Exception:
                pass

    modules = sorted(glob.glob(str(REPO / "data" / "FormaLLM" / "data" / "*" / "tla" / "*.tla")))
    if args.limit:
        modules = modules[: args.limit]

    calls = {"n": 0}
    base_proposer = make_invariant_proposer(chat_fn)

    def bounded_proposer(module_src, candidate, cti):
        if calls["n"] >= args.max_proposer_calls:
            return None
        calls["n"] += 1
        return base_proposer(module_src, candidate, cti)

    proposer = (lambda *a: None) if args.no_proposer else bounded_proposer

    deadline = time.time() + args.time_budget_min * 60
    summary = {"total": 0, "skipped": 0, "inductive": 0, "cegis_inductive": 0,
               "not_inductive": 0, "error": 0, "by_error": {}}

    print(f"[overnight] model={MODEL} modules={len(modules)} already_done={len(done)} "
          f"budget={args.time_budget_min}min proposer={'off' if args.no_proposer else 'on'}", flush=True)

    with out_path.open("a") as out:
        for i, path in enumerate(modules, 1):
            if time.time() > deadline:
                print(f"[overnight] time budget reached at module {i}", flush=True)
                break
            mod = str(Path(path).relative_to(REPO))
            if mod in done:
                continue
            row = {"module": mod, "ts": time.time()}
            try:
                src = Path(path).read_text(errors="replace")
                row["has_const"] = bool(_HAS_CONST.search(src))
                if not _HAS_NEXT.search(src) or not _HAS_TYPEOK.search(src):
                    row["status"] = "skipped"
                    row["reason"] = "no_next_or_typeok"
                    summary["skipped"] += 1
                else:
                    t0 = time.time()
                    r0 = check_inductive(src, "TypeOK", timeout=args.per_module_timeout)
                    row["census_secs"] = round(time.time() - t0, 1)
                    if r0.error:
                        row["status"] = "error"
                        row["error_class"] = classify_error(r0.error)
                        row["error"] = (r0.error or "")[:300]
                        summary["error"] += 1
                        summary["by_error"][row["error_class"]] = summary["by_error"].get(row["error_class"], 0) + 1
                    elif r0.inductive:
                        row["status"] = "inductive"
                        row["invariant"] = "TypeOK"
                        summary["inductive"] += 1
                    else:
                        row["cti"] = (r0.cti or "")[:300]
                        if args.no_proposer or calls["n"] >= args.max_proposer_calls:
                            row["status"] = "not_inductive"
                            summary["not_inductive"] += 1
                        else:
                            res = search_inductive_invariant(src, "TypeOK", proposer, max_iters=args.max_iters)
                            row["status"] = "cegis_" + res.status
                            row["invariant"] = res.invariant
                            row["iters"] = len(res.attempts)
                            if res.status == "inductive":
                                summary["cegis_inductive"] += 1
                            else:
                                summary["not_inductive"] += 1
            except Exception as e:  # never let one module kill the run
                row["status"] = "exception"
                row["error"] = repr(e)[:300]
                summary["error"] += 1
            summary["total"] += 1
            out.write(json.dumps(row) + "\n")
            out.flush()
            if i % 10 == 0:
                print(f"[overnight] {i}/{len(modules)} processed | proposer_calls={calls['n']} | {summary}", flush=True)

    summary["proposer_calls"] = calls["n"]
    (out_path.parent / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[overnight] DONE {summary}", flush=True)


if __name__ == "__main__":
    main()
