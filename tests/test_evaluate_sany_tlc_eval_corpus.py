import json
from pathlib import Path

import scripts.evaluate_sany_tlc_eval_corpus as evaluator


class _Semantic:
    distinct_states = 3
    invariants_checked = 1
    mutation_tested = True
    mutation_caught = True
    trivial_invariant = False


class _Result:
    def __init__(self, tier: str = "gold", diamond: bool = True) -> None:
        self.tier = tier
        self.is_diamond = diamond
        self.semantic = _Semantic()
        self.runtime_seconds = 0.1
        self.tlc_violations = []
        self.sany_errors = []


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _row(module: str) -> dict:
    return {
        "_module": module,
        "messages": [
            {"role": "developer", "content": "dev"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "channel": "final", "content": f"---- MODULE {module} ----\n====\n"},
        ],
    }


def test_replay_corpus_reports_all_gold_diamond(monkeypatch, tmp_path: Path) -> None:
    corpus = tmp_path / "eval.jsonl"
    _write(corpus, [_row("A"), _row("B")])
    seen = []

    def fake_validate(content: str, *, module_name: str, timeout: int):
        seen.append((module_name, timeout, content))
        return _Result()

    monkeypatch.setattr(evaluator, "validate_string", fake_validate)

    report = evaluator.replay_corpus(corpus=corpus, timeout=17)

    assert report["ok"] is True
    assert report["diamond_ok"] is True
    assert report["rows"] == 2
    assert report["checked"] == 2
    assert report["gold"] == 2
    assert report["diamond"] == 2
    assert [item[0] for item in seen] == ["A", "B"]
    assert all(item[1] == 17 for item in seen)


def test_replay_corpus_records_failures(monkeypatch, tmp_path: Path) -> None:
    corpus = tmp_path / "eval.jsonl"
    _write(corpus, [_row("Bad")])

    def fake_validate(_content: str, *, module_name: str, timeout: int):
        return _Result(tier="silver", diamond=False)

    monkeypatch.setattr(evaluator, "validate_string", fake_validate)

    report = evaluator.replay_corpus(corpus=corpus, timeout=10)

    assert report["ok"] is False
    assert report["gold"] == 0
    assert report["diamond"] == 0
    assert report["failures"][0]["module"] == "Bad"
    assert report["failures"][0]["tier"] == "silver"


def test_replay_corpus_reports_non_diamond_gold_without_failing_by_default(monkeypatch, tmp_path: Path) -> None:
    corpus = tmp_path / "eval.jsonl"
    _write(corpus, [_row("GoldButNotDiamond")])

    def fake_validate(_content: str, *, module_name: str, timeout: int):
        return _Result(tier="gold", diamond=False)

    monkeypatch.setattr(evaluator, "validate_string", fake_validate)

    report = evaluator.replay_corpus(corpus=corpus, timeout=10)
    strict = evaluator.replay_corpus(corpus=corpus, timeout=10, require_diamond=True)

    assert report["ok"] is True
    assert report["diamond_ok"] is False
    assert report["failures"] == []
    assert strict["ok"] is False
    assert strict["failures"][0]["module"] == "GoldButNotDiamond"


def test_replay_corpus_honors_limit(monkeypatch, tmp_path: Path) -> None:
    corpus = tmp_path / "eval.jsonl"
    _write(corpus, [_row("A"), _row("B")])
    calls = 0

    def fake_validate(_content: str, *, module_name: str, timeout: int):
        nonlocal calls
        calls += 1
        return _Result()

    monkeypatch.setattr(evaluator, "validate_string", fake_validate)

    report = evaluator.replay_corpus(corpus=corpus, timeout=10, limit=1)

    assert report["ok"] is True
    assert report["rows"] == 2
    assert report["checked"] == 1
    assert calls == 1


def test_replay_corpus_reports_repo_relative_corpus_path(monkeypatch) -> None:
    repo = Path(__file__).resolve().parents[1]
    corpus = repo / "data/processed/sany_tlc_pass_eval_v1.test.jsonl"
    _write(corpus, [_row("A")])

    def fake_validate(_content: str, *, module_name: str, timeout: int):
        return _Result()

    monkeypatch.setattr(evaluator, "validate_string", fake_validate)

    try:
        report = evaluator.replay_corpus(corpus=corpus, timeout=10)
        assert report["corpus"] == "data/processed/sany_tlc_pass_eval_v1.test.jsonl"
    finally:
        corpus.unlink(missing_ok=True)
