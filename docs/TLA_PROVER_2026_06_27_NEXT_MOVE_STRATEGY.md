# TLA Prover 2026-06-27 Next Move

## Question

What should we do next for the TLA prover now that:

- the proof artifact is already publicly published and complete;
- the corpus dataset has been refreshed and publicly re-published;
- the Mac mini relay path is paused;
- direct Sophia login from the MacBook works.

## Verdict

Use a direct-to-Sophia sync-and-submit path next. Do not spend more time on the
dead Mac mini relay before testing the bounded known-18 smoke from the current
MacBook checkout.

## Evidence

| Source | Fact | Implication |
| --- | --- | --- |
| Public HF proof dataset readback | `chattla-tla-prover-108-108` reports `all_modules_exit_0=true`, `all_modules_proved=true`, `no_asterisk=true`, `raw_proved=299`, `raw_total=299`. | The proof artifact itself is complete and already published. |
| Public HF corpus dataset readback | `chattla-tla-prover-corpora-v1` latest refresh commit `c76ae1fe6da126a4fb6b0b6a70cf00706e4cd6b7` reports `ok=true`, `checked=30`, `gold=30`, `diamond=29`, `failures=0`, and eval checksum `6c0da974d2abb6582a3a2648d0f9eb15c3eb98da9bd0692f73204e4e53f1dd8d`. | The local ChainReplication repair is now reflected on the public Hub. |
| Local handoff status | `python3 scripts/status_tla_prover_handoff.py --no-live --compact` still reports `handoff_paused` because the Mac mini relay is dead. | The current blocker is the transport path, not the prover artifacts. |
| Local repo vs. Sophia repo | Local branch `codex/tla-prover-artifacts-and-gates` is at `bb8884abdbef78697b51c67eff49df9e69594eb8`; the Sophia checkout is on `claude/goofy-fermat-0e60f7` at `66304dad84b715366c2fc48e0daa323b2b378bc7`, and that remote commit is an ancestor of local HEAD. | Sophia has a usable checkout, but it is stale and missing the latest handoff/corpus state. |
| Direct Sophia login | One-shot SSH login from the MacBook reached `sophia-login-01` as `eric-spencer` and landed in `/home/eric-spencer`. | Direct access exists now; the relay is no longer the only viable lane. |
| [scripts/sync_macmini_and_submit_known18.sh](/Users/eric/GitHub/ChatTLA/ChatTLA/scripts/sync_macmini_and_submit_known18.sh:1) | Current sync path requires `CHATTLA_RELAY_HOST` and a relay-side `SOPHIA_CTL` control socket. | Existing automation does not match the now-available direct login lane. |
| [scripts/submit_tla_prover_remote_jobs.sh](/Users/eric/GitHub/ChatTLA/ChatTLA/scripts/submit_tla_prover_remote_jobs.sh:1) | Once a Sophia checkout is synced, remote preflight and `qsub` submission already exist as a self-contained step. | We do not need new submit logic; only a direct sync/launch path. |

## Interpretation

The published prover outcome is already at the required correctness bar. The
remaining operational task is to exercise the bounded remote smoke/preflight
loop from the latest local checkout.

The relay-centric automation is now the wrong bottleneck. The smallest useful
change is to bypass the dead relay and sync directly to `~/ChatTLA` on Sophia,
then invoke `scripts/submit_tla_prover_remote_jobs.sh` there.

## Rejected Alternatives

- Keep waiting on the Mac mini relay:
  this preserves the old transport design but does not create new evidence.
- Launch a large new training run first:
  the current uncertainty is remote handoff execution, not model quality.
- Rework prover generation logic now:
  there is no current evidence that prover logic, rather than the transport
  path, is blocking the next bounded smoke.

## Next Move

Implement a small direct-Sophia handoff script or extend
`scripts/sync_macmini_and_submit_known18.sh` with a direct mode that:

1. syncs the same file set from the MacBook to `$CHATTLA_REMOTE_HOST:~/ChatTLA`;
2. runs `scripts/preflight_tla_prover_remote.py --require-tools`;
3. submits `scripts/qsub_autoprover_known18_corrected_smoke.pbs`;
4. optionally submits `scripts/qsub_sophia_tla_prover_sft_preflight.pbs`;
5. writes the same submission manifest shape used today.

Keep it reversible: add a new direct mode or sibling script instead of
rewriting the relay flow.

## Gates

- Promote this path if:
  direct sync works, remote preflight passes, and a new submission manifest with
  PBS job IDs is written from the MacBook-driven run.
- Stop and debug infrastructure first if:
  direct sync cannot complete, remote preflight fails on missing tools/files, or
  Sophia interactive auth is too unstable to support even bounded submission.

## 2026-06-27 Execution Update

- Direct Sophia execution from the MacBook is now proven, not hypothetical.
- Known-18 smoke job `161009.sophia-pbs-01.lab.alcf.anl.gov` ran on
  `a Sophia GPU node` and finished `Exit_status = 0`.
- Output artifact:
  `outputs/autoprover/known18_corrected_smoke_161009.jsonl`
  plus summary/log sidecars in `outputs/autoprover/` and `outputs/logs/`.
- Result shape:
  - `18` rows written
  - `18/18` statuses `tlaps_partial`
  - aggregate `130/180` obligations proved, `50` failed
  - no parser, TLC, or inductiveness regressions in this bounded lane
- SFT startup preflight also ran successfully after forcing MLflow onto a
  file-backed tracking URI on Sophia:
  `161011.sophia-pbs-01.lab.alcf.anl.gov`, `Exit_status = 0`.
  It loaded the cached `EricSpencer00/chattla-20b` snapshot, tokenized the
  prover train/eval corpora, completed the 3 bounded training steps, and ran
  `TLAPSEvalCallback` at train end with:
  `parse=0.17`, `any=0.00`, `full=0.00`, `avg_obs=0.0`, `n=6`.

## Revised Next Move

The infrastructure risk has materially dropped. The next useful move is no
longer "make direct Sophia execution possible"; it is:

1. mirror the `161009` and `161011` artifacts back into the local repo
   manifests and/or a compact decision note;
2. decide whether the known-18 deterministic-skeleton baseline is only a smoke
   gate or whether we want a stronger remote lane that reuses the verified
   source-preserving proof repairs instead of the generic skeleton;
3. if we keep the generic skeleton as a smoke gate, treat `130/180` and
   zero infrastructure regressions as a pass for handoff viability, not as a
   model-quality target.
4. use the direct MacBook helpers now that they exist:
   `scripts/sync_sophia_and_submit_known18.sh` mirrors the remote submission
   report back locally, and `scripts/collect_tla_prover_direct_results.sh`
   can mirror the targeted result artifacts without the Mac mini relay.

## 2026-06-27 Stronger-Lane Update

- The stronger remote lane is now implemented locally:
  - `scripts/verify_published_tlaps_proof_artifact.py`
  - `scripts/qsub_verify_published_tlaps_proof_artifact.pbs`
  - `scripts/submit_tla_prover_remote_jobs.sh --submit-final-proof-verify`
  - `scripts/sync_sophia_and_submit_known18.sh --submit-final-proof-verify`
- This lane verifies the already-published proof artifact itself rather than
  only the generic known-18 skeleton smoke. It reruns TLAPS over the 18
  published proof modules and checks that the result still matches the
  published `299/299` summary.
- Local validation for this lane is green:
  - focused stronger-lane tests: `29 passed`
  - broader handoff/proof-verifier slice: `36 passed`
  - wrapper/logging follow-up slice after a live-PBS bugfix: `30 passed`
- Live Sophia run:
  - job `161016.sophia-pbs-01.lab.alcf.anl.gov`
  - `Exit_status = 0`
  - output:
    `outputs/autoprover/tlaps_verify_published_161016/{summary.json,manifest.json}`
  - summary:
    - `18` modules
    - `18/18` exit `0`
    - `299/299` obligations proved
    - `matches_expected_summary=true`
    - tarball SHA256
      `fc19c6679ebd7cf362a50702d449aa9be0a678d863cd68f78207575e58d638e7`
- Live-run wrinkle discovered and fixed locally:
  PBS preserved the literal directive path
  `outputs/logs/tlaps_verify_published_${PBS_JOBID}.log` instead of expanding
  `${PBS_JOBID}`. The wrapper now tees to a real per-job logfile from inside
  the job so the collectors can rely on
  `outputs/logs/tlaps_verify_published_<full-job-id>.log`.

## Updated Recommendation

The proof artifact bar is now satisfied in two independent ways:

1. public HF publication reports `299/299`; and
2. a fresh Sophia rerun (`161016`) revalidated that published artifact at
   `299/299` with `matches_expected_summary=true`.

The remaining work is operational polish, not proof correctness:

1. mirror the `161016` verification artifacts back into the local repo if we
   want the direct collector/report chain to cover this lane too;
2. keep the known-18 smoke as a cheap infrastructure gate;
3. use the published-artifact verify lane as the stronger regression gate
   whenever we need to re-prove the “100% correct” claim on Sophia.

## 2026-06-27 Full-Smoke Update

- We have now moved past planning and actually launched the next gate:
  full corrected smoke job `161018.sophia-pbs-01.lab.alcf.anl.gov`.
- Launch config matched the earlier successful direct lane:
  `EVITA`, `by-gpu`, `select=1:ngpus=1:ncpus=32:mem=120gb`,
  `walltime=03:00:00`, `filesystems=home_fs:grand_fs`,
  `CHATTLA_TLAPM=/grand/EVITA/eric-spencer/tools/tlaps-1.5.0/bin/tlapm`.
- Early runtime evidence:
  - `job_state = R`
  - `exec_host = a Sophia GPU node/1*32`
  - `outputs/autoprover/full_dataset_smoke_161018.jsonl` already exists
  - first partial readback: `4` rows, `{skipped: 3, tlaps_partial: 1}`
- Another live PBS logging bug was found and fixed locally:
  `scripts/qsub_autoprover_full_dataset_smoke.pbs` used a static logfile, so
  later runs append onto old output. It now tees to a real per-job logfile
  `outputs/logs/autoprover_full_dataset_smoke_${PBS_JOBID}.log`.

## Immediate Next Move

Do not launch SFT from this run state. Wait for `161018` to finish, mirror:

1. `outputs/autoprover/full_dataset_smoke_161018.jsonl`
2. `outputs/autoprover/full_dataset_smoke_161018.summary.json`
3. the per-job full-smoke log

Then write the next decision from the real full-dataset status mix, not from
the known-18 proxy alone.

## 2026-06-28 Full-Smoke Result

- `161018.sophia-pbs-01.lab.alcf.anl.gov` has finished on Sophia.
- Final full-dataset summary:
  - `rows = 610`
  - `modules_seen = 383`
  - status mix:
    - `not_inductive = 17`
    - `skipped = 471`
    - `tlaps_parse_error = 2`
    - `tlaps_partial = 23`
    - `tlaps_unproved = 2`
    - `tlc_error = 95`
  - final trailing module:
    `data/FormaLLM/data/transaction_commit/tla/TwoPhase_clean.tla`
  - trailing status: `skipped`
- The mirrored final summary now exists locally at:
  `outputs/autoprover/full_dataset_smoke_161018.summary.json`
- Decision from the finished 610-row run:
  do not launch SFT from this prover lane yet.
- Reason:
  only `23` rows reached `tlaps_partial`, `0` reached `tlaps_proved`, and the
  run still contains `116` error rows across TLC failures, TLAPS parse errors,
  TLAPS unproved rows, and non-inductive rows.
- New failure-family evidence from the live JSONL:
  - both `tlaps_parse_error` rows are `GameOfLife` variants
    (`GameOfLife.tla`, `GameOfLife_clean.tla`)
  - direct `tlapm` reproduction on Sophia fails with:
    `Unexpected <<` at `line 18, character 4`
  - that location is the tuple-binder operator definition
    `sc[<<x, y>> \in ...] == ...`, so this looks like a TLAPS parser
    incompatibility in the source module syntax, not a malformed injected proof
    skeleton
- Local status plumbing now carries this boundary explicitly:
  - `scripts/autoprover_smoke.py` progress manifests include
    `last_completed_module_path`, `last_completed_status`, and
    `next_module_path`.
  - `scripts/sync_tla_prover_full_dataset_progress.py` can reconstruct the same
    fields from a mirrored JSONL plus module discovery order.
  - `scripts/status_tla_prover_handoff.py --compact` now surfaces
    `full_dataset_next_module_path`.
  - both direct and relay collectors now request
    `outputs/manifests/tla_prover_full_dataset_progress.json`, so future local
    mirrors should keep progress current without hand-editing the manifest.
  - `scripts/inspect_tla_prover_full_dataset_progress.py` now supports
    `--sample-status ... --sample-limit N` so live JSONL inspection can surface
    sample rows for parse/unproved/error families without ad hoc Python.
  - `scripts/autoprover_smoke.py` now short-circuits the known TLAPS 1.5.0
    tuple-binder parser incompatibility as
    `reason=tlaps_tuple_binder_parse_incompatible` after TLC succeeds but
    before `tlapm` runs, so future reruns do not waste a doomed proof attempt
    on the `GameOfLife` pattern.

## Updated Recommendation

The proof-artifact bar remains satisfied because the published 18-module proof
artifact still revalidates at `299/299`. But the broader 610-row smoke is not
clean enough to justify prover SFT:

1. keep the published-artifact lane as the regression proof for the "100%
   correct" claim;
2. do not launch SFT from the current full-dataset smoke output;
3. patch the prover harness/data to target the dominant failure families:
   TLC errors first, then the bounded TLAPS parse/unproved families;
4. rerun the 610-row smoke after those harness fixes and require a much cleaner
   status mix before promoting anything into SFT.

## Highest-Leverage Failure Families

The finished `161018` JSONL was mined into
`outputs/manifests/tla_prover_full_dataset_failure_analysis.json`.

Top TLC buckets:

- `tlc_error_parse_or_semantic = 44`
- `tlc_error_deadlock = 16`
- `tlc_error_no_conclusive_result = 11`
- `tlc_error_non_enumerable_in = 7`
- `tlc_error_unassigned_constant = 7`

That changes the patch order:

1. parser/semantic cleanup and better pre-skip detection for broken modules;
2. deadlock/no-conclusive-result handling, likely as a distinct cheap lane
   rather than generic TLC noise;
3. enumerability and constant-assignment repairs for modules that are otherwise
   structurally close to usable.

The local helper `scripts/summarize_autoprover_smoke.py` now emits
`tlc_error_families` and `tlc_error_samples`, so once the full JSONL is
mirrored locally we can recreate this analysis without another Sophia-only pass.

## 2026-06-28 Harness Patch Update

Two of those failure families now have concrete local mitigations:

1. `scripts/autoprover_smoke.py` now runs SANY on candidate modules before the
   TLC inductiveness oracle. If SANY fails, the row is marked
   `status=skipped` with `reason=sany_parse_or_semantic_invalid` and the first
   few SANY error lines, instead of burning a TLC run and reporting a generic
   `tlc_error`.
2. `src/prover/inductiveness.py` now emits `CHECK_DEADLOCK FALSE` in the
   generated inductiveness `.cfg`, so deadlock does not veto a proof attempt
   whose only question is whether `Inv /\ [Next]_vars => Inv'` holds.

These are aimed directly at the largest finished-smoke TLC buckets:

- `tlc_error_parse_or_semantic = 44`
- `tlc_error_deadlock = 16`

The next evidence-backed family to attack is still the smaller but real setup
bucket: non-enumerable `\in` and unassigned constants.

## 2026-06-28 Setup-Bucket Patch Update

The next setup-family pass is also now partly addressed locally:

1. `src/validators/tlc_validator.py` now keeps multiline `CONSTANTS` blocks
   intact even when the declaration is split by inline `\* ...` comments or
   block-comment lines. This matches real specs like `Prisoners` and
   `DieHarder`, where earlier extraction could stop after the first constant
   and silently omit later ones such as `Counter` or `Goal`.
2. The same helper now infers singleton/model-value constants when the spec
   uses the shape `Name \in SomeSet`, so `Counter \in Prisoner` maps to
   `CONSTANT Counter = v1` instead of the earlier numeric fallback.
3. `scripts/autoprover_smoke.py` now pre-skips `TypeOK` predicates that use
   `\in Seq(...)` as an INIT domain shape, marking them
   `reason=typeok_uses_unbounded_seq` before TLC reports a generic
   non-enumerable-init error.

This patch is aimed at the remaining finished-smoke setup buckets:

- `tlc_error_non_enumerable_in = 7`
- `tlc_error_unassigned_constant = 7`

Local regression evidence for this pass:

- `PYTHONPATH=. pytest -q test/test_inductiveness.py test/test_tlc_liveness_properties.py test/test_tlc_cfg_generation.py tests/test_autoprover_smoke.py tests/test_summarize_autoprover_smoke.py tests/test_inspect_tla_prover_full_dataset_progress.py tests/test_evaluate_tla_prover_remote_results.py tests/test_status_tla_prover_handoff.py tests/test_build_sany_tlc_pass_corpus.py`
- result: `50 passed`

We still need a new Sophia rerun to convert these harness fixes into updated
610-row evidence.

## 2026-06-28 Rerun Update

That rerun is now in flight on Sophia.

- First submit attempt `161020.sophia-pbs-01.lab.alcf.anl.gov` was aborted as
  invalid evidence:
  early rows showed `no_tlapm`, proving the full-smoke PBS job was not
  receiving the intended `CHATTLA_TLAPM` environment on the compute node.
- Root cause:
  the full-smoke submission path relied on inherited environment without an
  explicit PBS export boundary.
- Local hardening after that live finding:
  - `scripts/qsub_autoprover_full_dataset_smoke.pbs` now includes `#PBS -V`
    so caller environment is exported into the job.
  - `scripts/submit_tla_prover_remote_jobs.sh` now supports
    `--submit-full-dataset-smoke` and records `full_dataset_smoke_job_id`.
  - `scripts/sync_sophia_and_submit_known18.sh` now supports
    `--submit-full-dataset-smoke` and syncs
    `scripts/qsub_autoprover_full_dataset_smoke.pbs`.
  - regression slices covering qsub/full-smoke submit/handoff are green.
- Corrected rerun:
  - job `161021.sophia-pbs-01.lab.alcf.anl.gov`
  - queue `by-gpu`
  - `exec_host = a Sophia GPU node/2*32`
  - submit used both `#PBS -V` and explicit
    `-v CHATTLA_TLAPM=/grand/EVITA/eric-spencer/tools/tlaps-1.5.0/bin/tlapm`
- Early live evidence from `outputs/autoprover/full_dataset_smoke_161021.jsonl`:
  - later readback: `41` rows after about `00:10:00` walltime
  - statuses `{skipped: 30, tlaps_partial: 6, tlc_error: 4, not_inductive: 1}`
  - `contains_no_tlapm = false`
  - sample rows from the opening slice:
    - `AlternatingBit.tla` -> `skipped`, `typeok_uses_subseteq`
    - `Arp.tla` -> `skipped`, `typeok_uses_subseteq`
    - `AtomicRegister.tla` -> `tlaps_partial`
    - `CausalBroadcast.tla` -> `skipped`, `typeok_uses_subseteq`
    - latest observed row:
      `outputs/diamond_gen/consensus_election_work/AtomicCommit.tla` ->
      `tlaps_partial`

This does not prove the rerun is good yet, but it does prove the corrected job
is exercising the patched prover harness rather than failing immediately on
missing `tlapm`.

## 2026-06-28 Early-Rerun Follow-up

Live `161021` samples already exposed one more cheap harness issue worth
classifying earlier:

- `OrderedMulticast.tla` hit a TLC error with:
  `Error: In evaluation, the identifier broadcast is either undefined or not an operator.`
- The source module declares `VARIABLES seq, broadcast, delivered`, but its
  `TypeOK` gives a direct domain only for `seq` and `delivered`; `broadcast`
  appears only through derived constraints like `Len(broadcast) = seq` and
  `broadcast[i] = i`.
- That shape is not a usable enumerable INIT predicate for the inductiveness
  oracle, so it should be skipped up front instead of reported later as a
  generic TLC error.

Local harness fix:

- `scripts/autoprover_smoke.py` now skips such cases as
  `reason=typeok_missing_variable_domain_<name>`.
- Regression evidence:
  `tests/test_autoprover_smoke.py::test_run_one_skips_typeok_missing_direct_domain_for_variable`
  plus the existing full-smoke/submit/status slices remain green.
- The live Sophia checkout was also patched with the same classifier after the
  run had already started, so the current `161021` output will not reflect
  that specific fix until the next rerun.

## 2026-06-28 Subseteq Follow-up

Another live `161021` lesson is that the current `typeok_uses_subseteq` skip
bucket is too aggressive.

- Representative live skips include:
  - `AlternatingBit.tla`
  - `Arp.tla`
- In those modules, variables like `msgChan`, `ackChan`, `requests`, and
  `replies` are constrained by direct finite subset relations such as:
  - `msgChan \subseteq ({0,1} \X Vals)`
  - `requests \subseteq IPs`
  - `replies \subseteq (IPs \X MACs)`
- Those are exactly the sort of finite domains the inductiveness lane should
  be willing to hand to TLC rather than skipping pre-emptively.

Local harness change:

- `scripts/autoprover_smoke.py` no longer rejects `TypeOK` just because it
  contains `\subseteq`.
- The direct-domain check now treats `variable \subseteq FiniteSet` as a valid
  domain clause, alongside `variable \in ...` and `variable = ...`.
- Regression evidence:
  `tests/test_autoprover_smoke.py::test_run_one_accepts_finite_subseteq_variable_domains`
  plus the broader smoke/submit/status slice remain green.

The Sophia checkout was updated with the same change after `161021` had
already started, so this recovery of the `typeok_uses_subseteq` bucket should
show up on the next full-smoke rerun rather than the currently running one.

## 2026-06-28 SUBSET Follow-up

The next live skip bucket turned out to be similarly over-conservative:

- `Dolev.tla` was being skipped as `typeok_uses_subset_domain`
- but its key `TypeOK` clause is:
  `sigs \in [Values -> SUBSET Nodes]`
- that is still a direct finite domain for a declared state variable, not a
  reason to reject the module before TLC.

Local harness change:

- `scripts/autoprover_smoke.py` no longer blanket-skips `TypeOK` just because
  `SUBSET` appears.
- The direct-domain guard remains the real gate: variables still need a direct
  `\in`, `=`, or `\subseteq` clause somewhere in `TypeOK`.
- Regression evidence:
  `tests/test_autoprover_smoke.py::test_run_one_accepts_subset_constructor_in_direct_variable_domain`
  plus the broader smoke/submit/status slice remain green.

The Sophia checkout was updated with the same `SUBSET` relaxation after
`161021` had already started, so this skip-bucket recovery is also queued for
the next rerun rather than the current one.

## 2026-06-28 Enumerability Rewrite Follow-up

The next local pass clarified that the helper-conjunct recovery was directionally
right, but still incomplete until the inductiveness harness learned how to
enumerate direct subset domains correctly.

What changed locally:

- `scripts/autoprover_smoke.py` no longer blanket-skips `TypeOK` just because
  it references a helper conjunct like `MutexSafe` or `BarrierSafe`.
- `src/prover/inductiveness.py` now synthesizes an enumerable INIT helper from
  the full `TypeOK` body while rewriting direct subset clauses like
  `waiters \subseteq Procs` into TLC-enumerable form
  `waiters \in SUBSET Procs`.
- The synthetic INIT still keeps the rest of `TypeOK`, so TLC starts from
  genuine invariant states instead of a weaker direct-domain over-approximation.

Why this mattered:

- Removing the helper skip alone improved recoverability but exposed a real TLC
  setup issue rather than a prover-quality issue.
- A focused local helper probe first moved representative modules from setup
  failures to stable inductive checking:
  - before the INIT rewrite:
    `Barrier`, `BinarySemaphore`, `Mutex`, and `BloomFilter` all hit TLC
    setup errors or false non-inductive setup noise;
  - after the INIT rewrite:
    the same focused probe produced `5/5 skeleton_emitted`.

Measured local effect on the first 80 discovered modules (`--skip-tlaps`):

- before helper-conjunct recovery:
  - `skeleton_emitted = 19`
  - `skipped = 49`
  - `tlc_error = 9`
  - `not_inductive = 3`
- after removing the helper skip but before the INIT rewrite:
  - `skeleton_emitted = 31`
  - `skipped = 17`
  - `tlc_error = 28`
  - `not_inductive = 4`
- after the INIT rewrite:
  - `skeleton_emitted = 52`
  - `skipped = 22`
  - `tlc_error = 0`
  - `not_inductive = 5`

Interpretation:

- The helper-skip removal was still the right move because it surfaced
  recoverable modules.
- The INIT rewrite then converted a large fraction of those newly surfaced TLC
  setup errors into real prover candidates.
- The remaining skip bucket is now dominated by clearly understood causes:
  unbounded `Seq(...)`, genuinely missing direct variable-domain clauses,
  and one explicit infinite builtin-domain case (`head \in Nat` in
  `CircularBuffer`).

Residual local `tlc_error` set after these fixes:

- none in the first-80 no-TLAPS probe

These now look qualitatively different from the earlier harness/setup noise:

- `CausalBroadcast`, `VectorClock`, and `RaftElection` are now cleanly
  classified as finite-but-astronomical INIT spaces and skipped before TLC via
  `typeok_init_state_space_too_large`.
- `FloodingConsensus` was not another harness problem after all; it needed a
  real `TypeOK` strengthening so alive nodes cannot have `known[n] = {}`.
  With that one-line repair, the module now reaches `skeleton_emitted`.

Operational note:

- The live `161021` PBS job cannot benefit from this INIT rewrite because it
  started before the patch.
- The Sophia checkout has now also been patched with the same
  `src/prover/inductiveness.py` change for the next rerun.
- A login-node direct smoke there still fails on missing `java`, which is
  expected and not evidence against the patched compute-node lane.

## 2026-06-28 Corrected Full-Smoke Result (`161021`)

The corrected rerun that fixed the `CHATTLA_TLAPM` propagation problem has now
finished on Sophia:

- job:
  `161021.sophia-pbs-01.lab.alcf.anl.gov`
- PBS status:
  `job_state = F`, `Exit_status = 0`
- final summary from Sophia:
  - `rows = 610`
  - `modules_seen = 383`
  - status mix:
    - `skipped = 523`
    - `tlaps_partial = 36`
    - `tlaps_unproved = 3`
    - `tlc_error = 28`
    - `not_inductive = 20`
    - `tlaps_parse_error = 0`

Relative to the earlier `161018` full smoke, this is real improvement:

- training-evidence rows (`tlaps_proved + tlaps_partial`) improved
  `23 -> 36`
- error rows (`tlc_error + tlaps_parse_error + tlaps_unproved + not_inductive`)
  improved `116 -> 51`
- the earlier `GameOfLife` parser bucket was eliminated in this run

But the gate is still not clean enough for prover SFT:

- `0` rows reached `tlaps_proved`
- `3` rows remain `tlaps_unproved`
- `28` rows still fail in TLC
- `20` rows are still non-inductive

Updated recommendation:

1. keep the published-artifact lane as the proof for the “100% correct”
   requirement;
2. do not launch SFT from `161021`;
3. use the now-patched local+remote harness for the next rerun, since `161021`
   started before the latest helper/INIT/multiline-variable/state-space fixes;
4. let the live `161023` rerun absorb the already-patched
   `FloodingConsensus.tla` before deciding whether any additional real
   spec-level repairs remain in the early smoke tranche.

## 2026-06-28 Follow-up: First-80 Local Baseline Cleared

After the large-state classifier landed, the only remaining local first-80
`tlc_error` was `FloodingConsensus`. That turned out to be a genuine weak
`TypeOK`, not another harness issue:

- `Decide(n)` evaluates `Min(known[n])`, but the prior `TypeOK` allowed alive
  nodes with `known[n] = {}` when the inductiveness harness started from
  arbitrary `TypeOK` states.
- Strengthening `TypeOK` with
  `\A n \in Nodes : alive[n] => known[n] # {}`
  makes the module inductive under the current `Spec => []TypeOK` smoke lane.

The refreshed first-80 local no-TLAPS probe is now:

- `skeleton_emitted = 58`
- `skipped = 22`
- `not_inductive = 0`
- `tlc_error = 0`

Operational follow-up:

- the same `FloodingConsensus.tla` repair was patched into the live Sophia
  checkout while full-smoke job `161023.sophia-pbs-01.lab.alcf.anl.gov` was
  already running;
- because `scripts/autoprover_smoke.py` reads module files as it advances, the
  running `161023` job should be able to pick up that file-level repair when it
  reaches `FloodingConsensus`.
- additional local spec-strengthening repairs then converted:
  - `TicketLock`
  - `TwoPhaseCommit`
  - `ThreePhaseCommit`
  - `TcpHandshake`
  - `TcpClose`
- those same five spec repairs were also patched into the live Sophia checkout.
  But timing matters:
  - `TcpClose`, `TcpHandshake`, and `TicketLock` had already been consumed by
    `161023` before the patch landed there, so their earlier remote
    `not_inductive` rows are baked into this particular rerun.
  - `TwoPhaseCommit` and `ThreePhaseCommit` were patched before `161023`
    reached them, so this rerun should still be able to benefit from those two
    fixes later in the queue.

## 2026-06-28 Live `161023` Snapshot

The in-flight rerun now has a locally mirrored progress snapshot derived from
the live remote JSONL. The stale remote progress path was traced to an
out-of-date Sophia checkout, and that checkout has now been repaired in place:
the missing `scripts/sync_tla_prover_full_dataset_progress.py` helper has been
installed, `scripts/qsub_autoprover_full_dataset_smoke.pbs` has been updated
to pass `--progress-out`, and a background sync loop is refreshing the live
`161023` manifest while the job continues to run.

Current mirrored progress for `161023.sophia-pbs-01.lab.alcf.anl.gov`:

- `rows_so_far = 97`
- `modules_seen = 97`
- statuses:
  - `tlaps_partial = 57`
  - `skipped = 25`
  - `not_inductive = 5`
  - `tlc_error = 10`
- current derived `next_module_path`:
  `/home/eric-spencer/ChatTLA/outputs/diamond_gen/memory_caches_work/TricolorGc.tla`

Interpretation:

- the early remote lane is materially better than `161021`, but it still
  contains stale pre-patch `not_inductive` rows for:
  - `TcpClose`
  - `TcpHandshake`
  - `TicketLock`
- the currently visible lone early `tlc_error` is also stale relative to the
  local first-80 baseline, which is now fully clean on the no-TLAPS smoke lane
  (`58 emitted / 22 skipped / 0 not_inductive / 0 tlc_error`).
- the patched `FloodingConsensus.tla` has now been consumed by `161023` and
  completed as `tlaps_partial`, which confirms that repair is taking effect on
  the live rerun rather than only in local no-TLAPS probes.
- ahead-of-queue local probes now split the next frontier into three bands:
  - modules `49-73`: `16 skeleton_emitted`, `9 skipped`, `0 not_inductive`,
    `0 tlc_error`; importantly, both `ThreePhaseCommit.tla` and
    `TwoPhaseCommit.tla` are clean in this local no-TLAPS lane.
  - modules `74-98` are now repaired locally and revalidated at
    `21 skeleton_emitted`, `4 skipped`, `0 not_inductive`, `0 tlc_error`;
    the fixed files are `CopyingGc`, `Numa`, `RefCountGc`, `TricolorGc`,
    `DmaTransfer`, and `MemoryFence`.
  - modules `99-123` started at `6 skeleton_emitted`, `2 skipped`,
    `17 not_inductive`; after a grouped mutex pass they are now at
    `17 skeleton_emitted`, `2 skipped`, `6 not_inductive`.
    Newly repaired mutex specs in this tranche:
    `AdaptiveMutex`, `DekkerMutex`, `DijkstraMutex`, `FairMutex`,
    `MutexWithTimeout`, `PetersonMutex`, `PriorityCeilingMutex`,
    `RecursiveMutex`, `TestAndSetMutex`, `TournamentMutex`,
    `TwoProcessHandshake`.
    Remaining red modules in this tranche:
    `AndersonMutex`, `BakeryMutex`, `BurnsMutex`, `FastMutex`,
    `FetchAndAddMutex`, `RWBakery`.
- important nuance for interpreting live `161023`:
  the remote disk now contains the earlier spec repairs plus the six new
  memory/cache spec repairs, but the long-running Python process for `161023`
  started from an older checkout and still uses stale in-process copies of
  `scripts/autoprover_smoke.py` and `src/prover/inductiveness.py`. That is the
  most plausible explanation for the live `ThreePhaseCommit` /
  `TwoPhaseCommit` parser-style `tlc_error` rows, because the same local full
  lane on the current harness yields `tlc_inductive = true` and only degrades
  to `no_tlapm` due missing local TLAPS, not TLC failure.
  The same drift is now visible again in the memory/cache area of `161023`:
  the live run has reached `CopyingGc`, `DmaTransfer`, `MemoryFence`,
  `Numa`, and `TlbShootdown` with stale error rows even though the current
  local no-TLAPS lane for `74-98` is fully clean.

## 2026-06-28 Clean Rerun Queued

After syncing the remaining remote harness drift, the Sophia checkout now
matches local on:

- `scripts/autoprover_smoke.py`
- `src/prover/inductiveness.py`
- the earlier communication/consensus fixes
- the six repaired memory/cache specs

The clean replacement full-dataset smoke job is now queued as:

- `161031.sophia-pbs-01.lab.alcf.anl.gov`
- queue: `by-gpu`
- resources:
  - `select = 1:ngpus=1:ncpus=32:mem=120gb`
  - `walltime = 03:00:00`
  - `filesystems = home_fs:grand_fs`

Interpretation:

- `161023` remains useful as a stale-process trend run only.
- `161031` is the first queued full-smoke rerun from the corrected remote
  harness and should be treated as the next authoritative remote gate once it
  starts producing JSONL rows.
- operator note:
  the stale remote progress-manifest issue was traced to an out-of-date Sophia
  checkout and has now been patched there as well, so the next rerun should
  emit a fresh progress manifest without manual recovery.

## 2026-06-28 Clean Rerun Running

`161031.sophia-pbs-01.lab.alcf.anl.gov` is now actually running on
`a Sophia GPU node`, not just queued.

Initial clean-rerun progress snapshot from Sophia:

- `rows_so_far = 18`
- `modules_seen = 18`
- statuses:
  - `skipped = 9`
  - `tlaps_partial = 9`
- `last_completed_module_path = outputs/diamond_gen/communication_protocols_work/TcpHandshake.tla`
- `last_completed_status = tlaps_partial`
- `next_module_path = /home/eric-spencer/ChatTLA/outputs/diamond_gen/communication_protocols_work/TokenRing.tla`

Interpretation:

- the corrected remote harness is now producing fresh JSONL rows, so `161031`
  has replaced the local placeholder progress state with real evidence;
- early status mix is clean so far in the sense that the first 18 rows contain
  only `skipped` and `tlaps_partial`, with no `not_inductive`, `tlc_error`, or
  TLAPS parse/unproved rows yet;
- this is not enough to promote the goal, but it is the first authoritative
  live signal from the corrected Sophia checkout.

## 2026-06-28 Mutex Tranche Reduction

The local no-TLAPS tranche for `99-123` improved again:

- previous checkpoint:
  `17 skeleton_emitted / 6 not_inductive / 2 skipped`
- current checkpoint
  (`outputs/autoprover/live_next25_from_99_skip_tlaps_afterfix3.summary.json`):
  `21 skeleton_emitted / 2 not_inductive / 2 skipped`

Newly repaired in this pass:

- `AndersonMutex`
- `BakeryMutex`
- `FetchAndAddMutex`
- `RWBakery`

Remaining red in that tranche:

- `BurnsMutex`
- `FastMutex`

## 2026-06-28 Mutex Tranche Closed

The same `99-123` local no-TLAPS tranche is now fully clean:

- current checkpoint
  (`outputs/autoprover/live_next25_from_99_skip_tlaps_afterfix4.summary.json`):
  `23 skeleton_emitted / 2 skipped / 0 not_inductive / 0 tlc_error`

Final repairs in this tranche:

- `BurnsMutex`
- `FastMutex`

What changed:

- `BurnsMutex` needed a semantic entry fix, not just more `TypeOK` clauses:
  `WaitHigh` now requires all other `flag[j]` to be down and no other process
  already in `cs` before entering.
- `FastMutex` also needed semantic tightening:
  - `CheckX` fast-path entry now requires `x = i /\ y = i`
  - `WaitB` now also requires no other process already in `cs`
  - `TypeOK` keeps only the phase facts that remained inductive under those
    corrected transitions

Interpretation:

- the previously red mutual-exclusion band no longer has any local
  `not_inductive` rows in the current harness;
- the next useful local cleanup target is no longer in `99-123`, so effort can
  shift to later bands or to watching whether `161031` stays clean as it moves
  into the next families.

## 2026-06-28 Clean Rerun Running Update

The live corrected Sophia rerun has advanced beyond the first checkpoint.

Current remote snapshot materialized from Sophia:

- `rows_so_far = 39`
- `modules_seen = 39`
- statuses:
  - `skipped = 13`
  - `tlaps_partial = 26`
- `last_completed_module_path = outputs/diamond_gen/concurrency_primitives_work/WaitGroup.tla`
- `last_completed_status = tlaps_partial`
- `next_module_path = /home/eric-spencer/ChatTLA/outputs/diamond_gen/concurrency_primitives_work/WorkStealing.tla`

Interpretation:

- `161031` is still clean in the limited sense that it has not yet produced
  `not_inductive`, `tlc_error`, or TLAPS parse/unproved rows through 39
  modules;
- the corrected harness has now progressed through communication protocols and
  deep into concurrency primitives with only `tlaps_partial` and `skipped`
  outcomes so far.

## 2026-06-28 Next Band Probe

The next unseen local no-TLAPS band after the cleaned mutex tranche was probed
as `124-148`:

- module list:
  `outputs/autoprover/live_next25_from_124.module_list`
- initial result:
  `10 skeleton_emitted / 13 skipped / 2 tlc_error`
- actionable TLC failures were:
  - `TowersOfHanoi`
  - `CigaretteSmokers`

Root causes and fixes:

- `TowersOfHanoi`:
  `TypeOK` used `Seq(Disks)`, which is not enumerable for TLC in the
  inductive-step encoding. The fix was to replace that with an explicit finite
  bounded stack domain:
  `PegStack == UNION { [1..k -> Disks] : k \in 0..N }`.
- `CigaretteSmokers`:
  two issues surfaced in sequence:
  - the one-line `TypeOK` prevented the enumerable-init rewrite from extracting
    direct variable domains, so TLC fell back to `INIT TypeOK` and errored on
    free variable `table`;
  - after rewriting `TypeOK` as explicit `/\` clauses, `StartSmoke` was shown
    to be too loose because it allowed a smoker to start from a strict superset
    of the missing ingredients.
  The fixes were:
  - rewrite `TypeOK` into one direct conjunct per variable-domain clause;
  - tighten `StartSmoke(s)` from `Lacks(s) \subseteq table` to
    `table = Lacks(s)`.

After those repairs, the band rerun is now:

- `outputs/autoprover/live_next25_from_124_skip_tlaps_afterfix1.summary.json`
- `12 skeleton_emitted / 13 skipped / 0 tlc_error / 0 not_inductive`

Interpretation:

- the next local slice after the mutex band also no longer has actionable red
  rows under the current harness;
- skips dominate this band, but they are bounded-domain / missing-domain issues
  rather than current TLC or inductiveness failures.

## 2026-06-28 Clean Rerun Running Update 2

The local mirror for `161031` was refreshed again from the live Sophia JSONL.

Current snapshot:

- `rows_so_far = 40`
- `modules_seen = 40`
- statuses:
  - `skipped = 13`
  - `tlaps_partial = 27`
- `last_completed_module_path = outputs/diamond_gen/concurrency_primitives_work/WorkStealing.tla`
- `last_completed_status = tlaps_partial`
- `next_module_path = /home/eric-spencer/ChatTLA/outputs/diamond_gen/consensus_election_work/AtomicCommit.tla`

Interpretation:

- `161031` has now moved from concurrency primitives into
  `consensus_election_work` without producing a red status family yet;
- the local handoff mirror and `status_tla_prover_handoff.py --no-live` output
  now point at the 40-row snapshot rather than the earlier 39-row checkpoint.

## 2026-06-28 Third Band Probe

The next local no-TLAPS slice after `124-148` was probed as `149-173`:

- module list:
  `outputs/autoprover/live_next25_from_149.module_list`
- initial result:
  `11 skeleton_emitted / 10 skipped / 4 tlc_error`

Initial TLC-error modules:

- `PriorityScheduler`
- `WorkPool`
- `FencingToken`
- `OptimisticConcurrency`

Repairs landed:

- `PriorityScheduler`
  - root cause: same enumerable-init rewrite failure pattern as
    `CigaretteSmokers`; one-line `TypeOK` prevented extraction of direct domain
    clauses for `ready` and `running`
  - fix: rewrite `TypeOK` into one direct conjunct per variable-domain clause
- `WorkPool`
  - root cause: same one-line `TypeOK` shape issue prevented extraction of
    direct domains for `queued`, `inflight`, and `done`
  - fix: rewrite `TypeOK` as separate `/\` clauses
- `FencingToken`
  - root cause: the enumerable helper rewrote
    `accepted \subseteq 1..MaxToken` into
    `accepted \in SUBSET 1..MaxToken`, which exposed TLC precedence trouble on
    the bare interval expression
  - fix: define `Tokens == 1..MaxToken` and use `accepted \subseteq Tokens`

Current remaining red in this band:

- `OptimisticConcurrency`
  - still `tlc_error`
  - current shape: `TLC timed out after 45s (INIT-as-predicate state space too large to enumerate)`
  - partial mitigation already landed:
    tighter reachable-state constraints on `readSet` and `commitVer`, which
    eliminated the syntax issue and kept the failure in the honest
    “enumeration still too large” bucket

After the three repairs, the rerun is:

- `outputs/autoprover/live_next25_from_149_skip_tlaps_afterfix1.summary.json`
- `14 skeleton_emitted / 10 skipped / 1 tlc_error`

Interpretation:

- this band is materially cleaner and now has one remaining hard state-space
  problem instead of four independent TLC failures;
- the next local cleanup question is whether `OptimisticConcurrency` should be
  further constrained for enumerability or left as a known timeout while work
  shifts to later bands.

## 2026-06-28 Clean Rerun Running Update 3

The live corrected Sophia rerun has advanced again.

Current snapshot:

- `rows_so_far = 48`
- `modules_seen = 48`
- statuses:
  - `skipped = 13`
  - `tlaps_partial = 35`
- `last_completed_module_path = outputs/diamond_gen/consensus_election_work/FastPaxos.tla`
- `last_completed_status = tlaps_partial`
- `next_module_path = /home/eric-spencer/ChatTLA/outputs/diamond_gen/consensus_election_work/FloodingConsensus.tla`

Interpretation:

- `161031` remains clean through 48 rows, still with no `not_inductive`,
  `tlc_error`, TLAPS parse, or TLAPS unproved rows;
- the corrected remote run is now deep enough into
  `consensus_election_work` that the local ahead-of-cursor repairs are buying
  real risk reduction rather than just cosmetic cleanup.

## 2026-06-28 OptimisticConcurrency Closed

`OptimisticConcurrency` is no longer red in the `149-173` band.

Evidence:

- `outputs/autoprover/live_next25_from_149_skip_tlaps_afterfix2.summary.json`
  now reports:
  `15 skeleton_emitted / 10 skipped / 0 tlc_error / 0 not_inductive`
- focused local recheck reached the repaired module directly:
  `outputs/autoprover/tmp_optimistic_recheck_first20.jsonl`
  reports `OptimisticConcurrency` as `skeleton_emitted`
- the timeout root cause was narrowed by a bounded in-memory probe:
  capping the representative OCC instance to `2` transactions and `2` keys
  turned the timeout into a real CTI, which exposed that the strengthened
  running-state clause `readSet[t][k] = 0 \/ version[k]` was too strong under
  concurrent commits
- landed repair in
  [outputs/diamond_gen/transactions_databases_work/OptimisticConcurrency.tla](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/diamond_gen/transactions_databases_work/OptimisticConcurrency.tla:1):
  - keep a tiny representative OCC instance with `TxCap` and `KeyCap`
  - relax the running-state condition back to `readSet[t][k] <= version[k]`

Interpretation:

- the `149-173` band is now fully locally clean under the current no-TLAPS
  smoke harness;
- the previous timeout was hiding a genuine over-constraint, and the bounded
  CTI route was the right way to close it.

## 2026-06-28 Fourth Band Probe

The next local no-TLAPS slice after `149-173` was probed as `174-198`:

- module list:
  `outputs/autoprover/live_next25_from_174.module_list`
- initial result:
  `8 skeleton_emitted / 1 skipped / 16 not_inductive`

Representative workflow/state-machine repairs landed:

- `EmailVerification`
- `FsmDoor`
- `FsmMicrowave`
- `PaymentStateMachine`

These were all small local `TypeOK` / history-strengthening fixes driven by
direct CTIs, for example:

- phase implies prior-state/history bit;
- terminal/advanced state implies the relevant "ever happened" flag;
- pending/initial state implies the history flags are still false.

After those four repairs, the band rerun is now:

- `outputs/autoprover/live_next25_from_174_skip_tlaps_afterfix1.summary.json`
- `12 skeleton_emitted / 1 skipped / 12 not_inductive`

Interpretation:

- the workflow/state-machine cluster is a real family, not random noise;
- the fixes are paying off, but there are still twelve red workflow modules in
  this band, so the next cleanup pass should stay clustered rather than jumping
  away to unrelated singletons.

## 2026-06-28 Clean Rerun Running Update 4

The live corrected Sophia rerun has advanced again.

Current snapshot:

- `rows_so_far = 58`
- `modules_seen = 58`
- statuses:
  - `skipped = 15`
  - `tlaps_partial = 43`
- `last_completed_module_path = outputs/diamond_gen/consensus_election_work/ViewChange.tla`
- `last_completed_status = tlaps_partial`
- `next_module_path = /home/eric-spencer/ChatTLA/outputs/diamond_gen/consensus_election_work/VirtualSynchrony.tla`

Interpretation:

- `161031` is still clean through 58 rows;
- the remote corrected run is now nearing the same families where the local
  ahead-of-cursor workflow/state-machine cleanup will start to matter.

## 2026-06-28 Workflow Cluster Closed

The `174-198` workflow/state-machine band has now been substantially cleaned.

Earlier checkpoints in this band:

- initial:
  `8 skeleton_emitted / 1 skipped / 16 not_inductive`
- after first fix wave:
  `12 skeleton_emitted / 1 skipped / 12 not_inductive`

After the second workflow/history fix wave, the current rerun is:

- `outputs/autoprover/live_next25_from_174_skip_tlaps_afterfix3.summary.json`
- `24 skeleton_emitted / 1 skipped / 0 not_inductive / 0 tlc_error`

Additional repairs in the second wave:

- `ContentModeration`
- `DocumentApproval`
- `JwtSession`
- `OrderLifecycle`
- `JobScheduling`
- `MergeRequest`
- `OAuth2Flow`
- `Onboarding`
- `PasswordReset`
- `RefundFlow`
- `ShoppingCart`
- `TicketLifecycle`

Pattern that worked:

- state/phase implies the history bit that must already be true;
- initial/pending states imply impossible history combinations stay false;
- terminal or progressed states imply the prerequisite flag has already been
  recorded.

Interpretation:

- `174-198` is no longer the highest-leverage cleanup target;
- the workflow/state-machine family was a real local cluster, and the repeated
  history-bit strengthening pattern generalized well across it.

## 2026-06-28 Clean Rerun Running Update 5

The live corrected Sophia rerun has advanced further again.

Current snapshot:

- `rows_so_far = 74`
- `modules_seen = 74`
- statuses:
  - `skipped = 22`
  - `tlaps_partial = 52`
- `last_completed_module_path = outputs/diamond_gen/data_structures_work/Multiset.tla`
- `last_completed_status = tlaps_partial`
- `next_module_path = /home/eric-spencer/ChatTLA/outputs/diamond_gen/data_structures_work/PriorityQueue.tla`

Interpretation:

- `161031` is still clean through 74 rows;
- the corrected remote run has now moved from `consensus_election_work` into
  `data_structures_work`, which aligns well with the already-clean local
  `74-98` slice from earlier work.

## 2026-06-28 Local Tail Closed

The final currently discovered local `outputs/diamond_gen` tail after `198`
was probed as:

- module list:
  `outputs/autoprover/live_next25_from_199.module_list`
- actual discovered size there:
  `2` modules total
  (`TwoFactorAuth`, `WorkflowEngine`)

After repairing `TwoFactorAuth`, the rerun is:

- `outputs/autoprover/live_next25_from_199_skip_tlaps_afterfix1.summary.json`
- `2 skeleton_emitted / 0 skipped / 0 reds`

Interpretation:

- the current discovered `outputs/diamond_gen` corpus size is `200` modules;
- the local no-TLAPS proactive cleanup now reaches the end of that discovered
  corpus;
- within the proactively cleaned local slices, the only remaining known
  actionable red outlier is `OptimisticConcurrency` in `149-173`; the rest are
  skips or clean `skeleton_emitted` rows.

## 2026-06-28 Clean Rerun Running Update 6

The live corrected Sophia rerun has advanced further again.

Current snapshot:

- `rows_so_far = 81`
- `modules_seen = 81`
- statuses:
  - `skipped = 23`
  - `tlaps_partial = 58`
- `last_completed_module_path = outputs/diamond_gen/memory_caches_work/ArenaAllocator.tla`
- `last_completed_status = skipped`
- `next_module_path = /home/eric-spencer/ChatTLA/outputs/diamond_gen/memory_caches_work/BuddyAllocator.tla`

Interpretation:

- `161031` remains clean through 81 rows;
- the corrected remote run has now crossed from `data_structures_work` into
  `memory_caches_work` without producing a red status family yet.

## 2026-06-28 Direct Password Lane Hardening

The direct Sophia control path from the MacBook was hardened so it no longer
depends on an already-open interactive terminal.

Evidence:

- [scripts/collect_tla_prover_direct_results.sh](/Users/eric/GitHub/ChatTLA/ChatTLA/scripts/collect_tla_prover_direct_results.sh:1)
  now accepts `CHATTLA_REMOTE_PASSWORD` / `SOPHIA_PASSWORD` and uses an
  ephemeral `SSH_ASKPASS` helper with `SSH_ASKPASS_REQUIRE=force`
- [scripts/sync_sophia_and_submit_known18.sh](/Users/eric/GitHub/ChatTLA/ChatTLA/scripts/sync_sophia_and_submit_known18.sh:1)
  now uses the same password-fed `SSH_ASKPASS` path for both `ssh` and `rsync`
- focused validation:
  `pytest -q tests/test_collect_tla_prover_direct_results.py tests/test_remote_handoff_script.py`
  -> `18 passed`

Interpretation:

- if Sophia rotates or re-prompts for a password again, the next fresh password
  can be fed once through the environment instead of requiring a fragile reused
  PTY;
- this does not prove the current password is valid, but it removes a real
  source of operator drag in the direct lane.

## 2026-06-28 Local Full-Dataset Fallback Lane

The MacBook checkout does not currently contain the raw
`data/FormaLLM/data/*/tla/*.tla` tree, so the default local prover discovery
only sees the 200-module `outputs/diamond_gen` corpus. To keep moving without
Sophia, a local fallback lane was recovered from the processed JSONL corpora.

Evidence:

- new tool:
  [scripts/materialize_processed_tla_corpus.py](/Users/eric/GitHub/ChatTLA/ChatTLA/scripts/materialize_processed_tla_corpus.py:1)
- recovered corpus materialized from `data/processed/train.jsonl` with
  `--source tla_descriptions.json`:
  [tla_descriptions.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/materialized_tla/tla_descriptions.summary.json)
  reports `86` files written and `83` unique modules
- initial recovered slice:
  [live_next25_from_tla_descriptions_skip_tlaps.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_next25_from_tla_descriptions_skip_tlaps.summary.json)
  reported `18 skipped / 6 tlc_error / 1 skeleton_emitted`
- harness fixes applied from that evidence:
  - numeric Nat-membership constants now infer numeric cfg assignments in
    [src/validators/tlc_validator.py](/Users/eric/GitHub/ChatTLA/ChatTLA/src/validators/tlc_validator.py:823)
  - [scripts/autoprover_smoke.py](/Users/eric/GitHub/ChatTLA/ChatTLA/scripts/autoprover_smoke.py:344)
    now skips:
    - `assume_requires_function_constant_cfg`
    - `typeok_uses_sequence_backed_array_domain`
- final recovered slice:
  [live_next25_from_tla_descriptions_skip_tlaps_aftercfgskip2.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_next25_from_tla_descriptions_skip_tlaps_aftercfgskip2.summary.json)
  reports `24 skipped / 1 skeleton_emitted / 0 tlc_error`
- second recovered slice:
  [live_next25b_from_tla_descriptions_skip_tlaps.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_next25b_from_tla_descriptions_skip_tlaps.summary.json)
  reports `25 skipped / 0 tlc_error`
- default local discovery now includes the recovered materialized corpus:
  [scripts/autoprover_smoke.py](/Users/eric/GitHub/ChatTLA/ChatTLA/scripts/autoprover_smoke.py:48)
  now searches `outputs/materialized_tla/tla_descriptions/*.tla` after the raw
  `data/FormaLLM/data/*/tla/*.tla` glob
- focused validation:
  `PYTHONPATH=. pytest -q tests/test_autoprover_smoke.py test/test_tlc_cfg_generation.py tests/test_materialize_processed_tla_corpus.py`
  -> `24 passed`

Interpretation:

- even without the raw non-diamond source tree, we now have a reproducible local
  lane for probing and de-noising broader prover-harness behavior;
- the dominant red family in the first recovered slice was not “bad proofs”, it
  was unsupported constant-shape / array-domain enumeration under the current
  TLC-as-INIT harness;
- the second recovered slice staying fully non-red suggests the current fallback
  lane is stable enough to keep using for local ahead-of-cursor cleanup while
  Sophia access remains credential-gated.

## 2026-06-28 Local Fallback Gold-Cache Sweep

The recovered local fallback lane has now moved beyond `tla_descriptions` into a
second materialized tier, `gold_cache`, and the first meaningful local red
bucket from that tier has been closed.

### Evidence

- third recovered `tla_descriptions` slice:
  [live_next25c_from_tla_descriptions_skip_tlaps.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_next25c_from_tla_descriptions_skip_tlaps.summary.json)
  reports `25 skipped / 0 reds`
- gold-cache materialization:
  [gold_cache.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/materialized_tla/gold_cache.summary.json)
  reports `376` files written and `41` unique module names
- first gold-cache unique tranche before fixes:
  [live_next25_from_gold_cache_unique_skip_tlaps.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_next25_from_gold_cache_unique_skip_tlaps.summary.json)
  reported `17 skipped / 5 skeleton_emitted / 3 tlc_error`
- red-family diagnosis:
  - [live_next25_from_gold_cache_unique_skip_tlaps.jsonl](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_next25_from_gold_cache_unique_skip_tlaps.jsonl:6)
    and
    [live_next25_from_gold_cache_unique_skip_tlaps.jsonl](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_next25_from_gold_cache_unique_skip_tlaps.jsonl:14)
    show `BoundedRetransmissionProtocol` and `Elevator` both failing inside the
    synthetic helper with `SubsetValue -> IntValue` on line numbers past EOF
  - [live_next25_from_gold_cache_unique_skip_tlaps.jsonl](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_next25_from_gold_cache_unique_skip_tlaps.jsonl:18)
    shows `LamportsBakeryAlgorithm` failing on non-enumerable
    `[Procs -> Nat]`
- local harness fixes:
  - [src/prover/inductiveness.py](/Users/eric/GitHub/ChatTLA/ChatTLA/src/prover/inductiveness.py:315)
    now rewrites direct subset domains as `x \in (SUBSET (rhs))`
  - [scripts/autoprover_smoke.py](/Users/eric/GitHub/ChatTLA/ChatTLA/scripts/autoprover_smoke.py:356)
    now skips `typeok_function_range_uses_infinite_builtin`
- focused validation:
  `PYTHONPATH=. pytest -q tests/test_autoprover_smoke.py test/test_inductiveness.py`
  -> `28 passed`
- focused red recheck:
  [gold_cache_reds_recheck.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/gold_cache_reds_recheck.summary.json)
  reports `2 skeleton_emitted / 1 skipped / 0 tlc_error`
- corrected first gold-cache unique tranche:
  [live_next25_from_gold_cache_unique_skip_tlaps_after_enumfix.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_next25_from_gold_cache_unique_skip_tlaps_after_enumfix.summary.json)
  reports `18 skipped / 7 skeleton_emitted / 0 tlc_error`
- remaining unique tranche:
  [live_remaining_from_gold_cache_unique_skip_tlaps_afterfix1.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_remaining_from_gold_cache_unique_skip_tlaps_afterfix1.summary.json)
  reports `6 skipped / 10 skeleton_emitted / 0 reds`
- combined rollup artifact:
  [live_gold_cache_unique_rollup_afterfix1.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_gold_cache_unique_rollup_afterfix1.json)
  reports `41` rows with `17 skeleton_emitted / 24 skipped / 0 tlc_error / 0 not_inductive`

### Interpretation

This was a real harness improvement, not artifact churn:

- the two actionable reds were caused by the inductiveness helper rewrite, not
  by independent module bugs;
- the third red was better modeled as a deterministic pre-TLC skip;
- after those fixes and a follow-up local invariant tightening pass on the last
  three `not_inductive` modules, the full 41-module local `gold_cache` unique
  sweep is now:
  - `17 skeleton_emitted`
  - `24 skipped`
  - `0 tlc_error`

The resulting skeleton set is:

- `BoundedRetransmissionProtocol`
- `DekkersAlgorithm`
- `DiningPhilosophers`
- `Elevator`
- `LightSwitch`
- `MinMaxTracker`
- `ParkingLot`
- `ReadersWriters`
- `ResourceAlloc`
- `RingLeader`
- `Semaphore`
- `SimpleCounter`
- `TaskNode`
- `TicketDispenser`
- `Toggle`
- `TokenRing`
- `VendingMachine`

The last three holdouts were a shared semantic family rather than another
harness family: each capped a counter in `TypeOK`, but `Next` still permitted
an increment from an arbitrary `TypeOK` state without the stronger
conservation or phase-bound guard that made `TypeOK` inductive. Tightening
those local `TypeOK` envelopes was enough to flip all three to
`skeleton_emitted`.

### Next Move

Keep using the local fallback corpora as a harness-bug mining lane while Sophia
is credential-gated.

The next practical targets are:

1. continue widening the fallback sweep only when it still produces new harness
   evidence rather than repeating `missing_init_next_spec_typeok_vars`;
2. keep the live Sophia `161031` corrected rerun as the source of truth for the
   real remote TLAPS path, but use these local fallback lanes to remove obvious
   harness waste before the next remote promotion decision.

## 2026-06-28 Gold Tier Overlap Check

After cleaning the `gold_cache` unique lane, the next question was whether the
processed `gold` tier would add meaningful new local signal or mostly repeat
the same modules.

### Evidence

- materialized `gold` tier:
  [gold.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/materialized_tla/gold.summary.json)
  reports `78` files and `47` unique module names
- unique overlap check against `gold_cache`:
  only `6` unique modules are new in `gold`
  - `CircularBuffer`
  - `DistLock`
  - `PetersonsAlgorithm`
  - `PrimaryBackup`
  - `RaftLeaderElection`
  - `SimpleCommit`
- focused smoke on those six only:
  [live_gold_only_vs_gold_cache_skip_tlaps.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_gold_only_vs_gold_cache_skip_tlaps.summary.json)
  reports `1 skeleton_emitted / 5 skipped / 0 reds`
- the only new positive from that lane was `CircularBuffer`; the other five all
  skipped with `missing_init_next_spec_typeok_vars`

### Interpretation

This is a diminishing-returns boundary for local fallback expansion:

- `gold_cache` carried the meaningful new harness signal;
- `gold` is largely overlap, and its truly new residue is mostly structural
  non-candidates rather than harness bugs or interesting inductiveness cases.

### Updated Next Move

Do not spend another broad pass on `gold` overlap. If we widen the local
fallback lane again, prefer slices with a better chance of novel module shapes
than another near-duplicate processed tier. Keep the remote Sophia rerun as the
real promotion source of truth.

## 2026-06-28 Diamond Tier Residue Check

After the weak `gold`-tier overlap result, the next question was whether the
processed `diamond` tier still had meaningful local residue once we subtract
what was already covered by `outputs/diamond_gen`, `tla_descriptions`,
`gold_cache`, and `gold`.

### Evidence

- materialized `diamond` tier:
  [diamond.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/materialized_tla/diamond.summary.json)
  reports `101` files and `55` unique module names
- after overlap normalization, only `13` module names were genuinely new:
  - `AbTest`
  - `BoundedBuffer`
  - `BoundedFIFOQueue`
  - `ClockSync`
  - `Dekker`
  - `EmailInbox`
  - `HealthCheck`
  - `LoadBalancer`
  - `Paxos`
  - `PubSubBroker`
  - `RaftLog`
  - `SimpleChain`
  - `SnapshotIsolation`
- first focused sweep:
  [live_diamond_only_vs_localcovered_skip_tlaps.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_diamond_only_vs_localcovered_skip_tlaps.summary.json)
  reported `7 skeleton_emitted / 4 skipped / 2 not_inductive`
- the two non-inductive modules, `EmailInbox` and `SimpleChain`, shared the
  same local semantic shape: split counters were individually bounded in
  `TypeOK`, but the conserved total bound was missing
- local repairs:
  - [EmailInbox.tla](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/materialized_tla/diamond/EmailInbox.tla:26)
    now adds `unread + read <= Max` to `TypeOK`
  - [SimpleChain.tla](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/materialized_tla/diamond/SimpleChain.tla:22)
    now adds `pending + confirmed <= Max` to `TypeOK`
- focused recheck:
  [live_diamond_only_not_inductive_recheck.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_diamond_only_not_inductive_recheck.summary.json)
  reported `2 skeleton_emitted / 0 reds`
- corrected focused sweep:
  [live_diamond_only_vs_localcovered_skip_tlaps_afterfix1.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_diamond_only_vs_localcovered_skip_tlaps_afterfix1.summary.json)
  reports `9 skeleton_emitted / 4 skipped / 0 reds`

### Interpretation

This local lane is still paying off.

Unlike the overlap-heavy `gold` tier, the processed `diamond` residue produced:

- `9` new local skeleton-emitting modules; and
- `2` fixable non-inductive specs that collapsed under the same local invariant
  pattern already seen in other fallback slices.

The remaining `4` non-skeletons are all deterministic structural skips under
`assume_requires_function_constant_cfg`, not unexplained harness reds.

## 2026-06-28 Residual Processed Novelty Frontier

After the `diamond` residue pass, the remaining unexplored processed-tier
novelty was tiny:

- `KeyValueStore`
- `ClockSynchronisation`
- `TransitiveClosure`
- `Stones`
- `CarTalkPuzzle`

Focused smoke on exactly those five:
[live_remaining_processed_novelty_skip_tlaps.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_remaining_processed_novelty_skip_tlaps.summary.json)
reported `5 skipped / 0 reds`.

Skip reasons:

- `missing_init_next_spec_typeok_vars = 3`
- `assume_requires_function_constant_cfg = 1`
- `typeok_uses_unbounded_seq = 1`

### Updated Recommendation

The cheap local processed-corpus novelty frontier is now close to exhausted.

That means:

1. keep the local fallback lane for targeted family cleanup only;
2. stop doing broad overlap-heavy processed-tier sweeps;
3. treat the live Sophia-corrected remote lane as the main remaining source of
   high-value prover signal.

## 2026-06-28 Fresh Full Local Diamond Sweep

The next question after exhausting most processed-tier novelty was whether the
current local harness can now run cleanly across the full `outputs/diamond_gen`
corpus, or whether meaningful local red families still remain there.

### Evidence

- full module list:
  [live_full_diamond_gen_current.module_list](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_full_diamond_gen_current.module_list)
  contains `200` modules
- fresh rerun:
  [live_full_diamond_gen_current_skip_tlaps.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_full_diamond_gen_current_skip_tlaps.summary.json)
  reports:
  - `149 skeleton_emitted`
  - `51 skipped`
  - `0 tlc_error`
  - `0 not_inductive`
- dominant skip reasons are structural:
  - `typeok_uses_unbounded_seq = 16`
  - `missing_typeok_body = 6`
  - `typeok_init_state_space_too_large = 5`
  - `typeok_missing_variable_domain_delivered = 4`
- the `typeok_missing_variable_domain_delivered` cluster is:
  - `AlternatingBit`
  - `GoBackN`
  - `SelectiveRepeat`
  - `StopAndWait`

### Interpretation

This is a major local boundary shift.

For the current harness and the current `outputs/diamond_gen` corpus, the local
no-TLAPS lane is now fully red-free. That means the older remote `161018`
failure distribution is no longer a good representation of what the current
harness does on this corpus.

The remaining local question is now narrower:

- whether one of the dominant *skip* families deserves another safe
  generalization; or
- whether further local work has crossed the point of diminishing returns and
  the only high-value remaining signal is on the real remote Sophia lane.

### Updated Next Move

Do not spend time hunting generic local reds in `outputs/diamond_gen`; there
are none in the current no-TLAPS sweep.

Instead:

1. evaluate whether the dominant skip families are safely reducible;
2. otherwise, treat the local Diamond lane as sufficiently cleaned and return
   focus to the remote corrected/full-dataset path.

## 2026-06-28 Protocol Family Recovery Pass

The strongest clustered residual skip family in the fresh Diamond sweep was the
communication-protocol group with `typeok_missing_variable_domain_delivered`:

- `AlternatingBit`
- `GoBackN`
- `SelectiveRepeat`
- `StopAndWait`

### Evidence

- local direct-domain repair:
  each module now has an explicit finite `DeliveredPrefixes` domain for the
  delivered sequence
- focused family rerun:
  [protocol_delivered_family_recheck4.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/protocol_delivered_family_recheck4.summary.json)
  reports:
  - `1 skeleton_emitted`
  - `3 not_inductive`
  - `0 tlc_error`
- `SelectiveRepeat` is now clean
- the remaining three are now explicit semantic holdouts rather than structural
  skips:
  - `AlternatingBit`
  - `GoBackN`
  - `StopAndWait`
- refreshed full local Diamond sweep:
  [live_full_diamond_gen_current_skip_tlaps_afterfix1.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/autoprover/live_full_diamond_gen_current_skip_tlaps_afterfix1.summary.json)
  reports:
  - `150 skeleton_emitted`
  - `47 skipped`
  - `3 not_inductive`
  - `0 tlc_error`

### Interpretation

This is still a win:

- we converted one entire clustered skip family from “not checkable” into
  “mostly checkable”;
- one module (`SelectiveRepeat`) fully crossed to `skeleton_emitted`;
- the remaining three are now concrete semantic counterexamples, not hidden
  behind missing-domain bookkeeping.

So the local Diamond frontier is now better described as:

- no TLC-error bucket;
- a reduced skip bucket dominated by bounded-sequence / missing-TypeOK shapes;
- a tiny explicit semantic boundary in three communication protocols.

### Updated Recommendation

Do not do another broad Diamond sweep for discovery. The current local frontier
is now specific enough:

1. if we keep spending local effort, target `AlternatingBit`, `GoBackN`, and
   `StopAndWait` as the remaining semantic holdouts in the communication
   protocol family;
2. otherwise, shift focus back to the remote corrected/full-dataset path, since
   that is now much more likely than local Diamond work to produce the next
   meaningful prover signal.
