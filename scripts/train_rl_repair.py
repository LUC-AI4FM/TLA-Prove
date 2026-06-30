#!/usr/bin/env python3
"""GRPO training on gpt-oss-20b with repair prompts + improvement reward.

Instead of training the model to one-shot perfect specs (which gives
zero reward variance), this trains the model to REPAIR broken specs
given line-annotated verifier diagnostics.

Why this works:
  1. Dense reward — improvement delta gives variance even with 4 gens
  2. Easier task — fixing errors is simpler than generating from scratch
  3. Unlimited data — Ralph trajectories provide many repair pairs
  4. Curriculum — easy (SANY fixes) → medium → hard (TLC/semantic)

Architecture:
  - Base model: post-DPO checkpoint (same as train_rl_fullspec.py)
  - LoRA adapter: fresh r=8/alpha=16
  - Reward: repair_reward (improvement-based shaped reward)
  - Dataset: Ralph repair pairs from collect_ralph_trajectories.py
  - Trainer: TRL GRPOTrainer

Memory budget (2x RTX 8000, 49 GB each):
  - 20B bf16 ≈ 40 GB via device_map="auto"
  - 4 completions × 1024 tokens: similar to fullspec
  - Repair prompts longer (~1200 tokens) but completions shorter (1024)
  - Total: ~54-58 GB / 98 GB available

Run:
    python -m scripts.train_rl_repair --smoke           # 2-step sanity check
    python -m scripts.train_rl_repair --max-steps 300   # full run (~16h)
    python -m scripts.train_rl_repair --difficulty easy  # SANY-only curriculum
    python -m scripts.train_rl_repair --trajectory-file data/processed/tla_prover_repair_train_v1.jsonl

Default input behavior:
    Prefer data/processed/tla_prover_repair_train_v1.jsonl when present.
    Otherwise fall back to the available component repair corpora.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from scripts.build_tla_prover_repair_corpus import DEFAULT_PROFILE, VALID_PROFILES, default_out_for_profile

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MERGED_REPAIR_PAIRS = "data/processed/tla_prover_repair_train_v1.jsonl"
DEFAULT_MERGED_REPAIR_SUMMARY = "data/processed/tla_prover_repair_train_v1.summary.json"
DEFAULT_REPAIR_PAIRS = "data/processed/ralph_repair_pairs.jsonl"
DEFAULT_BENCHMARK_REPAIR_PAIRS = "data/processed/benchmark_repair_pairs_fc128best.jsonl"
DEFAULT_SMOKE_MODEL = "sshleifer/tiny-gpt2"
REQUIRED_RUNTIME_PROBES = (
    ("torch", "import torch\n"),
    ("yaml", "import yaml\n"),
    ("datasets.Dataset", "from datasets import Dataset\n"),
    ("peft.LoraConfig", "from peft import LoraConfig\n"),
    ("transformers.AutoModelForCausalLM", "from transformers import AutoModelForCausalLM\n"),
    ("transformers.AutoTokenizer", "from transformers import AutoTokenizer\n"),
    ("trl.GRPOConfig", "from trl import GRPOConfig\n"),
    ("trl.GRPOTrainer", "from trl import GRPOTrainer\n"),
)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _resolve_repo_path(path_str: str, repo_root: Path = _REPO_ROOT) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = repo_root / path
    return path


def _path_exists(path_str: str) -> bool:
    return _resolve_repo_path(path_str).is_file()


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _count_repair_rows(path: Path) -> tuple[int, set[str]]:
    rows = 0
    repair_ids: set[str] = set()
    if not path.is_file():
        return rows, repair_ids
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            rows += 1
            repair_id = json.loads(line).get("repair_id")
            if repair_id is not None:
                repair_ids.add(str(repair_id))
    return rows, repair_ids


def _probe_runtime_dependencies(
    probes: tuple[tuple[str, str], ...] = REQUIRED_RUNTIME_PROBES,
    *,
    python_executable: str | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    available: list[str] = []
    missing: list[dict[str, str]] = []
    timings: list[dict[str, Any]] = []
    python = python_executable or sys.executable
    timeout = timeout_s if timeout_s is not None else float(os.environ.get("CHATTLA_RUNTIME_IMPORT_TIMEOUT_S", "120"))
    for label, probe_script in probes:
        started_at = time.monotonic()
        try:
            completed = subprocess.run(
                [python, "-c", probe_script],
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            elapsed_s = round(time.monotonic() - started_at, 2)
            missing.append(
                {
                    "module": label,
                    "error": f"TimeoutExpired: import timed out after {timeout}s",
                }
            )
            timings.append({"module": label, "ok": False, "elapsed_s": elapsed_s})
            continue
        except Exception as exc:
            elapsed_s = round(time.monotonic() - started_at, 2)
            missing.append(
                {
                    "module": label,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            timings.append({"module": label, "ok": False, "elapsed_s": elapsed_s})
            continue

        elapsed_s = round(time.monotonic() - started_at, 2)
        if completed.returncode == 0:
            available.append(label)
            timings.append({"module": label, "ok": True, "elapsed_s": elapsed_s})
            continue

        detail = completed.stderr.strip() or completed.stdout.strip() or f"rc={completed.returncode}"
        missing.append({"module": label, "error": detail})
        timings.append({"module": label, "ok": False, "elapsed_s": elapsed_s})
    return {
        "ok": not missing,
        "available": available,
        "missing": missing,
        "timings": timings,
        "python_executable": python,
        "timeout_s": timeout,
    }


def _resolve_base_model() -> str:
    """Pick the best available MERGED base model in priority order."""
    env_base = os.environ.get("CHATTLA_BASE_MODEL")
    if env_base:
        return env_base
    candidates = [
        _REPO_ROOT / "outputs" / "merged_model_dpo_piecewise",
        _REPO_ROOT / "outputs" / "merged_model_repair",
        _REPO_ROOT / "outputs" / "merged_model_v20",
        _REPO_ROOT / "outputs" / "merged_model_v14",
        _REPO_ROOT / "outputs" / "merged_model_v13",
        _REPO_ROOT / "outputs" / "merged_model",
    ]
    for c in candidates:
        if c.is_dir() and (c / "config.json").is_file():
            return str(c)
    return "EricSpencer00/chattla-20b"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", default=None,
                        help="Base model path (auto-detected if omitted)")
    parser.add_argument("--smoke-model", default=DEFAULT_SMOKE_MODEL,
                        help="Small model ID used for bounded smoke runs when --smoke is set "
                        "and --model is omitted.")
    parser.add_argument("--output-dir", default="outputs/checkpoints_rl_repair")
    parser.add_argument("--max-steps", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=3e-6,
                        help="Slightly lower than fullspec for stability")
    parser.add_argument("--num-generations", type=int, default=4,
                        help="4 gens with repair prompts fits when Ollama is unloaded. "
                        "Use --num-generations 2 if sharing GPU with Ollama.")
    parser.add_argument("--per-device-batch-size", type=int, default=1)
    parser.add_argument("--max-completion-length", type=int, default=1024,
                        help="Repairs are shorter than from-scratch specs (1024 vs 1536). "
                        "Use 768 if sharing GPU with Ollama.")
    parser.add_argument("--beta", type=float, default=0.02,
                        help="Lower KL penalty — allow more deviation for repair task")
    parser.add_argument("--temperature", type=float, default=0.5,
                        help="Lower than fullspec — repairs need focus")
    parser.add_argument("--logging-steps", type=int, default=1)
    parser.add_argument("--save-steps", type=int, default=50)
    parser.add_argument("--difficulty", default="all",
                        choices=["easy", "medium", "hard", "all"],
                        help="Filter repair pairs by difficulty")
    parser.add_argument("--min-before-score", type=float, default=0.02,
                        help="Drop pairs with before_score below this — "
                        "unparseable specs leave the model with no improvement signal")
    parser.add_argument("--max-before-score", type=float, default=0.80,
                        help="Drop already-good pairs that leave no headroom")
    parser.add_argument("--max-prompt-tokens", type=int, default=1600,
                        help="Hard prompt-length filter — drops the long-tail "
                        "that blows up eager-attention memory (this version of "
                        "TRL has no GRPOConfig.max_prompt_length, so the only "
                        "defense is dataset-level filtering)")
    parser.add_argument("--device-map", default="auto",
                        help="Model placement passed to from_pretrained (default: auto). "
                        "Use cpu for bounded local smoke runs.")
    parser.add_argument("--dtype", default="auto",
                        choices=["auto", "bfloat16", "float16", "float32"],
                        help="Torch dtype for model loading. auto resolves to float32 on cpu/mps "
                        "and bfloat16 otherwise.")
    parser.add_argument("--trajectory-file", action="append", default=None,
                        help="Path to a repair-pairs JSONL. Repeat to mix multiple corpora. "
                        f"Defaults to `{DEFAULT_MERGED_REPAIR_PAIRS}` when present, otherwise the available component corpora.")
    parser.add_argument("--repair-corpus-profile", choices=VALID_PROFILES, default=DEFAULT_PROFILE,
                        help="Named repair-corpus profile to prefer when no explicit trajectory file is supplied.")
    parser.add_argument("--allowed-repair-bucket", action="append", default=None,
                        help="Optional repair bucket filter applied while loading repair prompts. Repeat to allow multiple buckets.")
    parser.add_argument("--include-benchmark-repair-pairs", action="store_true",
                        help="Also load the benchmark-derived repair corpus at "
                        f"`{DEFAULT_BENCHMARK_REPAIR_PAIRS}`.")
    parser.add_argument("--preflight-only", action="store_true",
                        help="Print a cheap local repair-corpus report and exit before loading tokenizer/model deps.")
    parser.add_argument("--smoke", action="store_true",
                        help="2 steps, no checkpoint, sanity-check the wiring")
    return parser


def build_runtime_config(args: argparse.Namespace) -> dict[str, Any]:
    implicit_smoke_model = bool(args.smoke and not args.model)
    model = args.smoke_model if implicit_smoke_model else (args.model or _resolve_base_model())

    device_map = args.device_map
    if implicit_smoke_model and device_map == "auto":
        device_map = "cpu"

    dtype = args.dtype
    if dtype == "auto":
        dtype = "float32" if device_map in {"cpu", "mps"} else "bfloat16"

    max_completion_length = args.max_completion_length
    max_prompt_tokens = args.max_prompt_tokens
    if implicit_smoke_model:
        max_completion_length = min(max_completion_length, 128)
        max_prompt_tokens = min(max_prompt_tokens, 512)

    return {
        "model": model,
        "device_map": device_map,
        "dtype": dtype,
        "trainer_bf16": dtype == "bfloat16",
        "max_completion_length": max_completion_length,
        "max_prompt_tokens": max_prompt_tokens,
        "implicit_smoke_model": implicit_smoke_model,
    }


def resolve_trajectory_files(args: argparse.Namespace, repo_root: Path = _REPO_ROOT) -> list[str]:
    path_exists = _path_exists if repo_root == _REPO_ROOT else lambda path: _resolve_repo_path(path, repo_root).is_file()
    if args.trajectory_file:
        files = list(args.trajectory_file)
        if args.include_benchmark_repair_pairs and DEFAULT_BENCHMARK_REPAIR_PAIRS not in files:
            files.append(DEFAULT_BENCHMARK_REPAIR_PAIRS)
        return files

    repair_corpus_profile = str(getattr(args, "repair_corpus_profile", DEFAULT_PROFILE) or DEFAULT_PROFILE)
    if repair_corpus_profile != DEFAULT_PROFILE:
        profile_path = str(default_out_for_profile(repair_corpus_profile, repo=repo_root).relative_to(repo_root))
        if path_exists(profile_path):
            return [profile_path]

    if path_exists(DEFAULT_MERGED_REPAIR_PAIRS):
        return [DEFAULT_MERGED_REPAIR_PAIRS]

    files = [path for path in [DEFAULT_REPAIR_PAIRS, DEFAULT_BENCHMARK_REPAIR_PAIRS] if path_exists(path)]
    if not files:
        files = [DEFAULT_REPAIR_PAIRS]
    if args.include_benchmark_repair_pairs and DEFAULT_BENCHMARK_REPAIR_PAIRS not in files:
        files.append(DEFAULT_BENCHMARK_REPAIR_PAIRS)
    return files


def build_preflight_report(
    args: argparse.Namespace,
    repo_root: Path = _REPO_ROOT,
    *,
    runtime_import_timeout_s: float | None = None,
) -> dict[str, Any]:
    trajectory_files = resolve_trajectory_files(args, repo_root=repo_root)
    raw_rows = 0
    unique_repair_ids: set[str] = set()
    file_reports: list[dict[str, Any]] = []
    missing_files: list[str] = []

    for path_str in trajectory_files:
        path = _resolve_repo_path(path_str, repo_root)
        exists = path.is_file()
        rows, ids = _count_repair_rows(path)
        raw_rows += rows
        unique_repair_ids.update(ids)
        if not exists:
            missing_files.append(path_str)
        file_reports.append(
            {
                "path": path_str,
                "exists": exists,
                "rows": rows,
                "unique_repair_ids": len(ids),
            }
        )

    using_merged_default = trajectory_files == [DEFAULT_MERGED_REPAIR_PAIRS]
    merged_summary_path = _resolve_repo_path(DEFAULT_MERGED_REPAIR_SUMMARY, repo_root)
    merged_summary = _read_optional_json(merged_summary_path) if using_merged_default else None
    if runtime_import_timeout_s is None:
        runtime_dependencies = _probe_runtime_dependencies()
    else:
        runtime_dependencies = _probe_runtime_dependencies(timeout_s=runtime_import_timeout_s)
    ok = not missing_files and raw_rows > 0
    if merged_summary is not None:
        ok = ok and bool(dict(merged_summary.get("health") or {}).get("ok"))
    ok = ok and runtime_dependencies["ok"]

    return {
        "schema": "chattla_tla_prover_repair_preflight_v1",
        "ok": ok,
        "repair_corpus_profile": str(getattr(args, "repair_corpus_profile", DEFAULT_PROFILE) or DEFAULT_PROFILE),
        "allowed_repair_buckets": sorted(
            {
                str(bucket).strip()
                for bucket in list(getattr(args, "allowed_repair_bucket", None) or [])
                if str(bucket).strip()
            }
        ),
        "trajectory_files": trajectory_files,
        "missing_files": missing_files,
        "raw_rows": raw_rows,
        "unique_repair_ids": len(unique_repair_ids),
        "using_merged_default": using_merged_default,
        "runtime_dependencies": runtime_dependencies,
        "files": file_reports,
        "merged_summary_path": DEFAULT_MERGED_REPAIR_SUMMARY if using_merged_default else None,
        "merged_summary": {
            "rows": merged_summary.get("rows"),
            "health": merged_summary.get("health"),
            "kept_rows_by_source": merged_summary.get("kept_rows_by_source"),
            "missing_sources": merged_summary.get("missing_sources"),
        } if merged_summary is not None else None,
    }


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    runtime = build_runtime_config(args)
    args.model = runtime["model"]

    if args.preflight_only:
        report = build_preflight_report(args)
        report["model"] = args.model
        report["runtime"] = runtime
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["ok"] else 2

    import torch
    import yaml
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    from src.rlvr_canary.repair_dataset import (
        format_repair_prompt,
        load_repair_prompts,
    )
    from src.rlvr_canary.repair_reward import register_before_scores, repair_reward

    if args.smoke:
        args.max_steps = 2
        args.save_steps = 1000
        args.logging_steps = 1

    # -- Tokenizer (needed for length-filter before dataset load) -----
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    # -- Dataset --------------------------------------------------------
    trajectory_files = resolve_trajectory_files(args)
    print(f"[rl-repair] loading repair prompts from {trajectory_files} ...")
    examples, before_scores = load_repair_prompts(
        trajectory_file=trajectory_files,
        difficulty=args.difficulty,
        max_examples=10 if args.smoke else None,
        min_before_score=args.min_before_score,
        max_before_score=args.max_before_score,
        max_prompt_tokens=runtime["max_prompt_tokens"],
        tokenizer=tokenizer,
        allowed_repair_buckets=args.allowed_repair_bucket,
    )
    if not examples:
        sys.exit(
            "No repair pairs found. Check filters or rebuild the selected corpora "
            "(for example collect_ralph_trajectories.py or build_benchmark_repair_pairs.py)."
        )
    print(f"[rl-repair] loaded {len(examples)} repair pairs "
          f"(difficulty={args.difficulty}, "
          f"score=[{args.min_before_score},{args.max_before_score}], "
          f"max_toks={args.max_prompt_tokens})")

    # Register before_scores with the reward function
    register_before_scores(before_scores)

    # -- LoRA config ----------------------------------------------------
    lora_cfg_path = _REPO_ROOT / "src" / "training" / "lora_config.yaml"
    with open(lora_cfg_path) as f:
        lora_cfg = yaml.safe_load(f)
    print(f"[rl-repair] LoRA: r={lora_cfg['r']}, alpha={lora_cfg['lora_alpha']}")

    peft_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        lora_dropout=lora_cfg.get("lora_dropout", 0.0),
        bias=lora_cfg.get("bias", "none"),
        target_modules=lora_cfg["target_modules"],
        task_type="CAUSAL_LM",
    )

    # -- Model ----------------------------------------------------------
    print(f"[rl-repair] loading base model {args.model} ...")

    # Pre-format repair prompts (same pattern as train_rl_fullspec.py)
    formatted_prompts: list[str] = []
    for ex in examples:
        formatted_prompts.append(format_repair_prompt(ex, tokenizer))

    # Dataset is pre-sorted by difficulty (easy first) for curriculum.
    # Disable shuffling in GRPOConfig to preserve ordering.
    train_ds = Dataset.from_list([
        {"prompt": p} for p in formatted_prompts
    ])
    print(f"[rl-repair] prompts pre-formatted: "
          f"avg {sum(len(p) for p in formatted_prompts) // len(formatted_prompts)} chars")

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=getattr(torch, runtime["dtype"]),
        device_map=runtime["device_map"],
    )
    model.config.use_cache = False

    # -- GRPO config ----------------------------------------------------
    gen_batch_size = args.per_device_batch_size * args.num_generations

    config = GRPOConfig(
        output_dir=args.output_dir,
        per_device_train_batch_size=gen_batch_size,
        generation_batch_size=gen_batch_size,
        gradient_accumulation_steps=1,
        learning_rate=args.learning_rate,
        max_steps=args.max_steps,
        num_generations=args.num_generations,
        max_completion_length=runtime["max_completion_length"],
        beta=args.beta,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        bf16=runtime["trainer_bf16"],
        report_to=["none"],
        remove_unused_columns=False,
        seed=20260410,
        temperature=args.temperature,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        generation_kwargs={
            "eos_token_id": [tokenizer.eos_token_id, 904],  # 904 = "===="
        },
    )

    # -- Trainer --------------------------------------------------------
    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        args=config,
        train_dataset=train_ds,
        reward_funcs=[repair_reward],
        peft_config=peft_config,
    )

    total_params = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[rl-repair] params: {total_params / 1e9:.1f}B total, "
          f"{trainable / 1e6:.1f}M trainable ({100 * trainable / total_params:.2f}%)")
    print(f"[rl-repair] starting GRPO: {args.max_steps} steps, "
          f"{args.num_generations} gens/prompt, lr={args.learning_rate}, "
          f"beta={args.beta}, temp={args.temperature}")

    trainer.train()

    # Save final checkpoint
    trainer.save_model(args.output_dir + "/final")
    print(f"[rl-repair] done -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
