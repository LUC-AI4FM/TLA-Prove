# AI4FM Public Dataset Surface

This note captures the current public dataset surface that ChatTLA can use
without private infrastructure.

## Current public sources

- `FormaLLM`: <https://github.com/LUC-AI4FM/FormaLLM>
- `tla-dataset-pipeline`: <https://github.com/LUC-AI4FM/tla-dataset-pipeline>
- `tla-dataset-pipeline` DVC metadata:
  <https://raw.githubusercontent.com/LUC-AI4FM/tla-dataset-pipeline/main/dvc.lock>

## Verified current counts

These values come from the local inspection report at
`outputs/manifests/ai4fm_public_dataset_surface.json`.

- `FormaLLM`
  - git head: `e74c2ed`
  - `205` canonical metadata entries
  - `71` families
  - `191` unique model names
  - `410` `.tla` files under `data/*/tla/*.tla`
  - `187` cleaned comment prompt files
- `tla-dataset-pipeline`
  - git head: `59bd533`
  - DVC `pull` surface: `data/raw`, `2628` files
  - DVC `parse` input snapshot: `data/raw`, `227` files
  - DVC `parse` output surface: `data/parsed`, `3979` files

## Public discovery manifest

ChatTLA now also materializes the checked-in public discovery recipe as:

- `data/processed/ai4fm_public_discovery_manifest_v1.jsonl`
- `data/processed/ai4fm_public_discovery_manifest_v1.summary.json`

Current live summary:

- `11` operational seed repos
- `7` configured org seeds and `9` configured user seeds present for auditability
- `5` checked-in search queries
- `18` unique public repo records from the live recipe
- `4` of the `5` shipped repository-search queries currently return zero repos

That mismatch matters: the pipeline config includes `orgs` and `users`, but the
checked-in loader currently ignores them and only uses `repos`. The summary
also captures the current repository-search hit counts so we can distinguish the
public discovery recipe from the larger DVC-backed raw/parsed corpus.

## How ChatTLA should use them

- Treat `FormaLLM` as the canonical public prompt/spec supervision layer.
- Treat `ai4fm_public_discovery_manifest_v1` as the public repo-level discovery
  lane we can ingest directly today.
- Treat `tla-dataset-pipeline` DVC counts as the broader public parsing lane.
- Do not collapse these into one dataset category: the 205-entry `FormaLLM`
  benchmark is curated, the discovery manifest is a public GitHub repo roster,
  and the DVC surface is a larger extraction and transformation inventory.

## Rebuild

```bash
python3 scripts/inspect_ai4fm_public_dataset_surface.py
python3 scripts/build_ai4fm_public_discovery_manifest.py
```

The discovery manifest builder expects a local checkout of
`LUC-AI4FM/tla-dataset-pipeline` at `/tmp/LUC-AI4FM-tla-dataset-pipeline` by
default. Pass `--pipeline-repo /path/to/tla-dataset-pipeline` if your checkout
is elsewhere.
