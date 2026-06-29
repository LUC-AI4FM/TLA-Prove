import json
import subprocess
from pathlib import Path

from scripts.diagnose_sany_tlc_pass_corpus import diagnose_corpus


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "diagnose_sany_tlc_pass_corpus.py"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _row(module: str, final: str | None = None, evidence: dict | None = None) -> dict:
    final = final or f"---- MODULE {module} ----\nEXTENDS Naturals\n====\n\nSPECIFICATION Spec\n"
    return {
        "_tier": "sany_tlc_pass",
        "_module": module,
        "_evidence": {
            "sany_pass": True,
            "tier": "gold",
            "is_diamond": True,
            "distinct_states": 3,
            "invariants_checked": 1,
            "mutation_caught": True,
            "trivial_invariant": False,
            **(evidence or {}),
        },
        "messages": [
            {"role": "developer", "content": "dev"},
            {"role": "user", "content": "user"},
            {"role": "assistant", "channel": "analysis", "content": "analysis"},
            {"role": "assistant", "channel": "final", "content": final},
        ],
    }


def test_diagnose_corpus_accepts_strong_sany_tlc_rows(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    _write_jsonl(corpus, [_row("TrainA"), _row("TrainB")])
    _write_jsonl(holdout, [{"module": "Holdout"}])

    result = diagnose_corpus(corpus=corpus, holdout=holdout, summary=None)

    assert result["ok"] is True
    assert result["rows"] == 2
    assert result["duplicate_modules"] == []
    assert result["holdout_overlap"] == []
    assert result["module_header_mismatches"] == []
    assert result["corpus"] == str(corpus)
    assert result["holdout"] == str(holdout)


def test_diagnose_corpus_flags_leakage_and_weak_rows(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    _write_jsonl(
        corpus,
        [
            _row("Leak"),
            _row("Dup"),
            _row("Dup"),
            _row("Mismatch", final="---- MODULE Other ----\n====\n"),
            _row("Weak", evidence={"mutation_caught": False, "distinct_states": 1}),
        ],
    )
    _write_jsonl(holdout, [{"module": "Leak"}])

    result = diagnose_corpus(corpus=corpus, holdout=holdout, summary=None)

    assert result["ok"] is False
    assert result["duplicate_modules"] == ["Dup"]
    assert result["holdout_overlap"] == ["Leak"]
    assert result["module_header_mismatches"] == ["Mismatch"]
    assert "Weak" in result["weak_evidence_modules"]


def test_diagnose_cli_writes_report(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    out = tmp_path / "diagnostic.json"
    _write_jsonl(corpus, [_row("TrainA")])
    _write_jsonl(holdout, [])

    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--corpus",
            str(corpus),
            "--holdout",
            str(holdout),
            "--summary",
            str(tmp_path / "missing.summary.json"),
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["rows"] == 1
    assert payload["summary"] == str(tmp_path / "missing.summary.json")
