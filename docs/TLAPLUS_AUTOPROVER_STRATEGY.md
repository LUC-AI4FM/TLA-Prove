# TLA+ Autoprover Strategy

## Question

What is the practical prover direction for ChatTLA?

## Short Answer

Use a verifier-guided prover pipeline, not free-form proof generation.

The current working shape is:

1. extract a target theorem or safety property;
2. search for an inductive strengthening with deterministic tooling;
3. emit deterministic TLAPS proof skeletons;
4. validate every candidate with `tlapm`;
5. use model output only for narrow repair steps.

## Why This Direction

The repo already contains the right building blocks:

- `src/prover/cegis.py` for counterexample-guided invariant search
- `src/prover/skeleton.py` for deterministic proof skeleton generation
- `src/validators/tlaps_validator.py` for proof validation

That architecture fits the actual failure mode we see in practice: broad
language-model proof generation is noisy, but verifier-guided narrowing can be
checked and iterated.

## Current Public Takeaways

- Safety and invariance proofs are the first useful target.
- Deterministic proof shaping currently has higher leverage than broad
  whole-proof generation.
- Counterexample-guided strengthening and proof decomposition are the core
  mechanisms worth investing in.
- The proof lane and the spec-generation lane should be judged separately:
  proof validation may succeed even while benchmark spec generation remains far
  from publish-ready.

## What Counts as Real Progress

Autoprover progress should be backed by checked artifacts such as:

- exact theorem/module inputs
- generated proof skeletons
- raw `tlapm` results
- counterexamples or failed obligations
- repair attempts tied to specific verifier feedback

Anything weaker than that should be treated as exploration, not a promoted
prover result.

## Current Recommendation

Keep the prover lane narrow and evidence-backed:

- deterministic skeletons first
- verifier feedback second
- model-based repair only at failed leaves

This keeps the prover path auditable and compatible with a public quality bar.
