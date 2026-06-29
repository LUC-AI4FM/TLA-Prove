# AI4FM Public Surface Live Verification (2026-06-29)

## Verdict

The current public AI4FM surface still supports ChatTLA's existing split:

- `FormaLLM` remains the canonical `205`-entry benchmark layer.
- The older `1800+` wording is still visible in a stale `ARCHITECTURE.md` note,
  but it does not match the current committed public metadata.
- The public `LUC-AI4FM` org currently exposes `8` repos; `FormaLLM`,
  `TLA-Prove`, and `tla-dataset-pipeline` are the `3` corpus-relevant ones.
- The broader public GitHub expansion story is still best represented by the
  larger `TLA-Prove` and seed-repo lanes: `2757` committed public JSONL rows,
  `2110` public seed `.tla` files, `2108` usable seed modules, and `18` live
  discovery-manifest repo records.

## Evidence

### FormaLLM

- Live repo head on 2026-06-29:
  `b159f5df093e7ed71f4793bba99459b97a2bb23d`
- Raw metadata count:
  - `data/all_models.json` still resolves to `205` canonical rows
  - `Input/train.json`, `Input/val.json`, `Input/test.json` still sum to `205`
    as `143 + 30 + 32`
- Stale architecture note still present:
  - `doc/ARCHITECTURE.md` still says `Metadata for 1800+ specifications`
- Public site still aligns with the `205`-entry benchmark layer:
  - <https://ai4fm.cs.luc.edu/>
  - <https://ai4fm.cs.luc.edu/papers/llm-tla-evaluation/>
- Primary upstream files:
  - <https://raw.githubusercontent.com/LUC-AI4FM/FormaLLM/main/data/all_models.json>
  - <https://raw.githubusercontent.com/LUC-AI4FM/FormaLLM/main/Input/train.json>
  - <https://raw.githubusercontent.com/LUC-AI4FM/FormaLLM/main/Input/val.json>
  - <https://raw.githubusercontent.com/LUC-AI4FM/FormaLLM/main/Input/test.json>

### TLA-Prove

- Live repo head on 2026-06-29:
  `d1b5142422cfab2ce9a2eba9522d6221776378d6`
- Fresh live report from
  `python3 scripts/inspect_ai4fm_public_tlaprove_corpora.py`:
  - tracked public training/eval surface: `2350` rows across `6` files
  - full committed public JSONL surface: `2757` rows across `19` files
  - additional committed public rows outside the tracked corpora: `407`
  - current public benchmark surface: `20` benchmark items
  - explicit holdout artifact still present as `30` rows in
    `data/processed/diamond_eval_holdout.jsonl`

### LUC-AI4FM org surface

- Fresh live org snapshot from `python3 scripts/inspect_ai4fm_org_surface.py`:
  - `8` public repos in `LUC-AI4FM`
  - `3` corpus-relevant repos: `FormaLLM`, `TLA-Prove`,
    `tla-dataset-pipeline`
  - `5` adjacent public repos: `FormaLLM-Reverse`, `paper-parse`, `webpage`,
    `ralph-tla`, `.github`
- The strongest currently untracked public corpus-adjacent lane is still the
  `407` rows across the `13` committed `TLA-Prove` JSONL files outside the
  tracked import slice (`data/toy/*` + `outputs/diamond_gen/*`). The new
  opt-in importer path materializes that broader committed surface as `2757`
  raw rows or `1010` deduped rows, which is only `5` unique normalized rows
  beyond the existing tracked `1005`-row import lane.

### tla-dataset-pipeline discovery / seed lanes

- Live pipeline repo head on 2026-06-29:
  `4ac5620f7ef425285ca5a8d91304c9b4da5ca56f`
- Fresh live discovery refresh from
  `python3 scripts/build_ai4fm_public_discovery_manifest.py`:
  - `18` unique repo records
  - `4` of the `5` shipped search queries still return zero repositories
- Current checked-in public seed recipe:
  - `11` explicit repo seeds
  - `7` org seeds
  - `9` user seeds
  - `5` search queries
- Primary upstream files:
  - <https://raw.githubusercontent.com/LUC-AI4FM/tla-dataset-pipeline/main/config/seeds/repos.yaml>
  - <https://raw.githubusercontent.com/LUC-AI4FM/tla-dataset-pipeline/main/config/seeds/queries.yaml>
  - <https://raw.githubusercontent.com/LUC-AI4FM/tla-dataset-pipeline/main/dvc.lock>
- Existing checked-in seed-file/module surfaces remain consistent with the live
  interpretation:
  - `2110` public `.tla` files
  - `2108` usable module rows
  - `98` SANY-clean prover-candidate rows

## Interpretation

The public AI4FM story is still two-layered:

1. `205` canonical benchmark entries for direct supervised/eval work.
2. A broader public GitHub corpus surface well above `1800` items, but spread
   across different artifact types and repos rather than represented by the
   canonical `FormaLLM` metadata file alone.

That means the existing ChatTLA wording is still directionally correct:

- keep `205` as the canonical `FormaLLM` count;
- treat `1800+` as stale if it is used to describe `FormaLLM` itself;
- if someone means the broader public AI4FM GitHub surface, the closest direct
  public evidence today is the larger `TLA-Prove` JSONL surface plus the
  `tla-dataset-pipeline` seed/DVC recipe, not the canonical `FormaLLM`
  metadata file;
- when someone means the broader public GitHub surface, use the reproducible
  higher-signal lanes (`2757`, `2110`, `2108`, `18`) instead of repeating the
  stale `1800+` shorthand.

## Commands used

```bash
python3 scripts/inspect_ai4fm_org_surface.py
python3 scripts/inspect_ai4fm_public_tlaprove_corpora.py
python3 scripts/build_ai4fm_public_discovery_manifest.py
python3 - <<'PY'
import json, urllib.request, subprocess

def rows(obj):
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        data = obj.get("data")
        if isinstance(data, list):
            return len(data)
        return len(obj)
    return None

base = "https://raw.githubusercontent.com/LUC-AI4FM/FormaLLM/main/"
with urllib.request.urlopen(base + "data/all_models.json", timeout=30) as r:
    all_models = json.load(r)
counts = {}
for name in ["train", "val", "test"]:
    with urllib.request.urlopen(base + "Input/" + name + ".json", timeout=30) as r:
        counts[name] = rows(json.load(r))
print(rows(all_models), counts, sum(counts.values()))
print(subprocess.run(
    ["git", "ls-remote", "https://github.com/LUC-AI4FM/FormaLLM.git", "HEAD"],
    text=True, capture_output=True, check=True
).stdout.split()[0])
print(subprocess.run(
    ["git", "ls-remote", "https://github.com/LUC-AI4FM/tla-dataset-pipeline.git", "HEAD"],
    text=True, capture_output=True, check=True
).stdout.split()[0])
PY
```
