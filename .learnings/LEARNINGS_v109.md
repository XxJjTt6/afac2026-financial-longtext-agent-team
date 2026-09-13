# V109 Learnings

1. Public-family deduplication is not calibration. A 5/7 mode can still be wrong on an
   isolated official sentinel.
2. Candidate ranking must first measure each source against official forced-correct qids.
3. Complete option-level source audits outrank an uncalibrated public vote. They retain
   `reg_a_004=C` and `ins_a_006=A`, and promote `fc_a_004=ACD`.
4. Six available attempts are an upper bound, not six files to pre-submit. Each candidate
   after P0 is conditional on the newest exact official result.
5. The first current-day submission must reproduce the 95-question V85 baseline before
   cross-day equations are reused.
