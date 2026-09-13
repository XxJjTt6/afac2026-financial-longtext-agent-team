# Learnings V95

- A no-change isolated contrast does not reveal the gold label, but it can exclude the tested incumbent from a downside-sensitive baseline under exact-match scoring.
- `fc_a_014` should be audited as a set-valued multi-choice label. Testing only `A` and `B` missed the plausible omitted `C` clause.
- Under deadline pressure, prefer one known-wrong incumbent plus one source-grounded unseen replacement over another confounded bundle.
