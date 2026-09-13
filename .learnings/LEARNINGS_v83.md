# V83 Learnings

1. A previously discovered dataset defect must become a persistent quarantine rule. Recording it in a report is not enough if later solvers can silently restore the invalid closed-world assumption.
2. Exhausting all legal single-choice outputs at equal official score falsifies the full local-binding/exact-match/one-legal-gold contract. It never identifies a remaining legal gold.
3. Add a permanent no-match or unscored state to every qid before fitting leaderboard equations. Adding it only after infeasibility is already used to derive labels is too late.
4. V39 correctly found `fc_a_015` has source truth set `AB`; V80 and V81 were wasted because that finding was not carried forward as a hard exclusion.
5. V51 is valuable negative evidence: after neutralizing the fc15 B-to-D change, its six other replacements each lost one point. Freeze those six V36 incumbents.
6. `fc_a_004=ACD` is bounded to a 0 or +1 delta from V36 under the current conditional model. This is a diagnostic candidate, not a guaranteed improvement.
7. Never reuse an old candidate CSV by filename alone. The V30 `fc_a_004=ACD` file also changes four unrelated qids and is not a clean single-qid probe.
