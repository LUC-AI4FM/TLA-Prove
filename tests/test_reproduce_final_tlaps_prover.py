import tempfile
import unittest
import unittest.mock
from pathlib import Path

from scripts.reproduce_final_tlaps_prover import (
    ModuleResult,
    _default_base_proof_dir,
    _public_proof_dir_ref,
    _public_tool_ref,
    build_proof_set,
    parse_tlaps_output,
    run_tlaps_module,
    summarize_results,
)


class ReproduceFinalTlapsProverTests(unittest.TestCase):
    def test_parse_success_aggregates_zero_obligation_noise(self) -> None:
        output = "\n".join(
            [
                "[INFO]: All 0 obligations proved.",
                "[INFO]: All 85 obligations proved.",
            ]
        )

        parsed = parse_tlaps_output(output)

        self.assertEqual(parsed.proved, 85)
        self.assertEqual(parsed.total, 85)
        self.assertEqual(parsed.failed, 0)
        self.assertTrue(parsed.proved_all)

    def test_parse_partial_counts_failed_total(self) -> None:
        output = "\n".join(
            [
                "[INFO]: All 4 obligations proved.",
                "[ERROR]: 2/6 obligations failed.",
            ]
        )

        parsed = parse_tlaps_output(output)

        self.assertEqual(parsed.proved, 8)
        self.assertEqual(parsed.total, 10)
        self.assertEqual(parsed.failed, 2)
        self.assertFalse(parsed.proved_all)

    def test_summarize_results_requires_exit_zero_and_all_proved(self) -> None:
        results = [
            ModuleResult(
                module="A",
                path="A.tla",
                exit_code=0,
                runtime_seconds=1.2,
                proved=3,
                total=3,
                failed=0,
                timed_out=False,
                raw_log="raw/A.log",
            ),
            ModuleResult(
                module="B",
                path="B.tla",
                exit_code=0,
                runtime_seconds=0.5,
                proved=4,
                total=5,
                failed=1,
                timed_out=False,
                raw_log="raw/B.log",
            ),
        ]

        summary = summarize_results(results, require_no_asterisk=True)

        self.assertEqual(summary["modules"], 2)
        self.assertEqual(summary["exit_0"], 2)
        self.assertEqual(summary["exit_nonzero"], 0)
        self.assertEqual(summary["raw_proved"], 7)
        self.assertEqual(summary["raw_total"], 8)
        self.assertFalse(summary["all_modules_exit_0"])
        self.assertTrue(summary["no_asterisk"])

    def test_build_proof_set_overwrites_named_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            base.mkdir()
            (base / "AtomicRegister.tla").write_text("base atomic\n", encoding="utf-8")
            (base / "Other.tla").write_text("other\n", encoding="utf-8")
            atomic = root / "AtomicRegister_source_preserving_choose.tla"
            atomic.write_text("repaired atomic\n", encoding="utf-8")
            out = root / "out"

            build_proof_set(
                base_proof_dir=base,
                replacements={"AtomicRegister.tla": atomic},
                proof_dir=out,
            )

            self.assertEqual(
                (out / "AtomicRegister.tla").read_text(encoding="utf-8"),
                "repaired atomic\n",
            )
            self.assertEqual((out / "Other.tla").read_text(encoding="utf-8"), "other\n")

    def test_run_tlaps_module_accepts_repo_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=".") as tmp:
            root = Path(tmp)
            proof_dir = root / "proofs"
            proof_dir.mkdir()
            tla = proof_dir / "A.tla"
            tla.write_text("---- MODULE A ----\n====\n", encoding="utf-8")
            fake_tlapm = root / "fake_tlapm.py"
            fake_tlapm.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env python3",
                        "from pathlib import Path",
                        "import sys",
                        "target = Path(sys.argv[-1])",
                        "if not target.is_absolute():",
                        "    print(f'not absolute: {target}', file=sys.stderr)",
                        "    raise SystemExit(4)",
                        "if not target.is_file():",
                        "    print(f'missing: {target}', file=sys.stderr)",
                        "    raise SystemExit(3)",
                        "print('[INFO]: All 1 obligation proved.')",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            fake_tlapm.chmod(0o755)

            result = run_tlaps_module(
                tla_file=tla.resolve().relative_to(Path.cwd()),
                tlapm=fake_tlapm.resolve(),
                raw_dir=root / "raw",
                threads=1,
                timeout=10,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.proved, 1)
            self.assertEqual(result.total, 1)

    def test_public_refs_strip_host_suffixes_and_absolute_tool_paths(self) -> None:
        self.assertEqual(
            _public_proof_dir_ref(
                Path(
                    "outputs/autoprover/"
                    "tlaps_mixed_targeted_t1_160785.sophia-pbs-01.lab.alcf.anl.gov/proofs"
                )
            ),
            "outputs/autoprover/tlaps_mixed_targeted_t1_160785/proofs",
        )
        self.assertEqual(_public_tool_ref("/opt/tlaps/bin/tlapm"), "tlapm")

    def test_default_base_proof_dir_prefers_host_neutral_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            outputs = repo / "outputs" / "autoprover"
            preferred = outputs / "tlaps_mixed_targeted_t1_160785" / "proofs"
            preferred.mkdir(parents=True)

            with unittest.mock.patch("scripts.reproduce_final_tlaps_prover.REPO", repo):
                with unittest.mock.patch.dict("os.environ", {}, clear=True):
                    self.assertEqual(_default_base_proof_dir(), preferred)


if __name__ == "__main__":
    unittest.main()
