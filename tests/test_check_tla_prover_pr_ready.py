from pathlib import Path

from scripts.check_tla_prover_pr_ready import build_commands, scan_files


def test_scan_files_flags_private_hosts_and_paths(tmp_path: Path) -> None:
    candidate = tmp_path / "script.sh"
    candidate.write_text(
        "\n".join(
            [
                "ssh " + "eric" + "spencer@" + "100." + "117.97.102",
                "export CHATTLA_TLAPM=/grand/" + "EVITA/user/tools/tlapm",
                "dataset=EricSpencer00/chattla-tla-prover-corpora-v1",
            ]
        ),
        encoding="utf-8",
    )

    findings = scan_files([candidate])

    assert len(findings) == 3
    assert {finding["pattern"] for finding in findings} == {
        "private_ssh_user",
        "private_tailscale_or_lan_ip",
        "site_storage_path",
    }


def test_build_commands_includes_compact_prover_remote_suite() -> None:
    commands = build_commands()
    joined = "\n".join(" ".join(command) for command in commands)

    assert "python3 -m py_compile" in joined
    assert "tests/test_remote_handoff_script.py" in joined
    assert "tests/test_preflight_tla_prover_remote.py" in joined
    assert "tests/test_build_tla_prover_manifest.py" in joined
