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

## How ChatTLA should use them

- Treat `FormaLLM` as the canonical public prompt/spec supervision layer.
- Treat `tla-dataset-pipeline` as the broader public discovery and parsing lane.
- Do not collapse these into one dataset category: the 205-entry `FormaLLM`
  benchmark is curated, while the pipeline surface is a larger extraction and
  transformation inventory.

## Rebuild

```bash
python3 scripts/inspect_ai4fm_public_dataset_surface.py
```
