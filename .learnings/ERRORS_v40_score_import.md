# V40 Score Import Error

- Attempted to import a non-existent `expected_score` helper from
  `agent.evaluation.score_diagnostics`.
- The repository exposes score inference utilities but not that direct helper.
- Fix: compute the documented score formula directly for build manifests and
  keep the numeric projection covered by artifact tests.
