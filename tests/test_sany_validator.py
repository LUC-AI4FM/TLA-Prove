from src.validators.sany_validator import _parse_errors
from src.validators.sany_validator import validate_file


def test_parse_errors_keeps_meaningful_sany_detail() -> None:
    output = """
****** SANY2 Version 2.2 created 08 July 2020

Parsing file /tmp/AddTwo.tla
Labels added.
Fatal errors while parsing TLA+ spec in file /tmp/AddTwo.tla

In module AddTwo

Cannot find source file for module TLAPS imported in module AddTwo.
*** Errors: 1

In module AddTwo

Cannot find source file for module TLAPS imported in module AddTwo.
"""

    assert _parse_errors(output) == [
        "Cannot find source file for module TLAPS imported in module AddTwo.",
        "*** Errors: 1",
    ]


def test_validate_file_runs_from_module_directory(monkeypatch, tmp_path) -> None:
    jar = tmp_path / "tla2tools.jar"
    jar.write_text("", encoding="utf-8")
    tla = tmp_path / "SpecA.tla"
    tla.write_text("---- MODULE SpecA ----\n====\n", encoding="utf-8")

    seen = {}

    class _Completed:
        stdout = "Semantic processing of module SpecA\n"
        stderr = ""

    def fake_run(cmd, *, cwd, capture_output, text, timeout):
        seen["cmd"] = cmd
        seen["cwd"] = cwd
        return _Completed()

    monkeypatch.setattr("src.validators.sany_validator.subprocess.run", fake_run)

    result = validate_file(tla, jar=jar)

    assert result.valid is True
    assert seen["cmd"][-1] == "SpecA.tla"
    assert seen["cwd"] == str(tmp_path)
