---
license: apache-2.0
tags:
  - tla-plus
  - tlaps
  - theorem-proving
  - formal-methods
  - chattla
pretty_name: ChatTLA TLA+ Prover 108/108 Proof Artifact
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/train.jsonl
---

# ChatTLA TLA+ Prover 108/108 Proof Artifact

This repository contains a reproducible ChatTLA TLAPS proof artifact for the
final no-asterisk normalized 108/108 TLA+ prover result.

## Verified Result

- Modules: 18
- TLAPS exit 0: 18
- Raw obligations proved: 299/299
- Source-preserving repairs: `AtomicRegister` and `IdempotencyKey`
- Reproduction PBS job: `160816` on Sophia

## Contents

- `data/train.jsonl`: viewer-friendly module-level proof results with a stable
  schema
- `metadata/summary.json`: full module-level TLAPS result summary
- `metadata/manifest.json`: command inputs and package checksum metadata
- `tlaps_reproduced_final_160816.tar.gz`: proof modules, raw TLAPS logs,
  `summary.json`, and `manifest.json`
- `reproduce_final_tlaps_prover.py`: reproducible proof-set rebuild and TLAPS
  validation command
- `qsub_reproduce_final_tlaps_prover.pbs`: Sophia PBS wrapper
- `SHA256SUMS`: checksums for the uploaded files

## Reproduce

On Sophia, from the ChatTLA checkout:

```bash
qsub scripts/qsub_reproduce_final_tlaps_prover.pbs
```

The core command is:

```bash
python3 scripts/reproduce_final_tlaps_prover.py \
  --tlapm "${CHATTLA_TLAPM:-tlapm}" \
  --out-dir outputs/autoprover/tlaps_reproduced_final_${JOBNUM} \
  --package outputs/autoprover/tlaps_reproduced_final_${JOBNUM}.tar.gz \
  --threads 1 \
  --timeout 900 \
  --expected-modules 18
```

The package checksum for `tlaps_reproduced_final_160816.tar.gz` is:

```text
20ca68ea4caf304b42d5b45fbaeadefc55eb0a17fd1fd9991db27ed741a5d46c
```
