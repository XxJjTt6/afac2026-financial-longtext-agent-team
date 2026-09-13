# LEARNINGS V116

## Route correction

- Retire V115 before submission.
- A same-family public official A/B self-report already showed
  `fc_a_004 AD->ACD` was score-neutral at 92; ranking `AD` as a primary candidate
  inverted the evidence hierarchy.
- Use the two locally forced-wrong V85 incumbents, `fc_a_004=CD` and
  `fc_a_014=AB`, as the only initial search surface.

## Submission design

- P1 tests `fc_a_004=D` and `fc_a_014=BC` together.
- P2 isolates `fc_a_004=D` only when P1 is below 97.
- The pair/isolation scores exactly decode the two hit indicators under the
  zero-downside binding model.
- Spend the final four slots on exactly one result-gated family; never mix
  fallback families.
- Every CSV has a distinct total-token watermark and SHA-256.

## Evidence boundary

- The zero-downside property is conditional on the registered historical
  screenshot-to-local-file bindings.
- Public repository score reports have no official server digest.
- Neither semantic agreement nor a model's confidence is an official-gold
  probability.
