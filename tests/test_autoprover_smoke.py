from pathlib import Path

import scripts.autoprover_smoke as smoke


MINI_MODULE = """---- MODULE Mini ----
EXTENDS Naturals
VARIABLE x
vars == <<x>>
Init == x = 0
Next == x' = x + 1
Spec == Init /\\ [][Next]_vars
TypeOK == x \\in Nat
====
"""


def test_injected_typeok_theorem_extends_tlaps() -> None:
    proof_module = smoke._inject_typeok_theorem(MINI_MODULE, "OBVIOUS")

    assert "EXTENDS Naturals, TLAPS" in proof_module
    assert "THEOREM ChatTLA_TypeOKSafety == Spec => []TypeOK" in proof_module


def test_discover_accepts_explicit_module_list(tmp_path: Path) -> None:
    first = tmp_path / "First.tla"
    second = tmp_path / "Second.tla"
    first.write_text("---- MODULE First ----\n====\n", encoding="utf-8")
    second.write_text("---- MODULE Second ----\n====\n", encoding="utf-8")
    module_list = tmp_path / "modules.txt"
    module_list.write_text(
        f"\n# comment\n{first}\n{second}\n{first}\n",
        encoding="utf-8",
    )

    paths = smoke._discover_from_module_lists([module_list], limit=0)

    assert paths == [first.resolve(), second.resolve()]


def test_discover_module_list_treats_repo_relative_paths_as_repo_relative(tmp_path: Path) -> None:
    module_list = tmp_path / "modules.txt"
    module_list.write_text("scripts/autoprover_smoke.py\n", encoding="utf-8")

    paths = smoke._discover_from_module_lists([module_list], limit=0)

    assert paths == [(smoke.REPO / "scripts" / "autoprover_smoke.py").resolve()]


def test_run_one_validates_temp_file_with_matching_module_name(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "Mini.tla"
    module_path.write_text(MINI_MODULE, encoding="utf-8")

    class Inductive:
        inductive = True
        error = None
        cti = None

    class Tlaps:
        tier = "proved"
        obligations_total = 1
        obligations_proved = 1
        obligations_failed = 0
        timed_out = False
        errors = []
        raw_output = "[INFO]: All 1 obligation proved."

    seen: dict[str, str] = {}

    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")
    monkeypatch.setattr(smoke, "_tlapm_path", lambda: "/bin/true")

    def fake_validate_string(content: str, *, module_name: str, **_kwargs) -> Tlaps:
        seen["module_name"] = module_name
        seen["header"] = content.splitlines()[0]
        return Tlaps()

    monkeypatch.setattr(smoke, "validate_string", fake_validate_string)

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=True)

    assert row["status"] == "tlaps_proved"
    assert seen == {"module_name": "Mini", "header": "---- MODULE Mini ----"}
