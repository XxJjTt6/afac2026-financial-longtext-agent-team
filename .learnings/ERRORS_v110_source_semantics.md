# V110 Source-Semantics Correction

## [ERR-20260718-110] stale source audit reused after a later correction

**Logged**: 2026-07-18T00:00:00+08:00
**Priority**: critical
**Status**: resolved
**Area**: evaluation

### Summary

V109 reused V99's `fc_a_004=ACD` and `fc_a_014=BC` source labels even though V100 had
already corrected the strict labels to `AC` and `B`.

### Root Cause

The latest source-audit version was not treated as authoritative. Two option-level details
were missed: 66.38% exceeds a strict 66% upper bound, and 2031 is conditional on a put or
call rather than the ordinary series-one redemption date.

### Correction

V110 keeps the byte-identical P0 control, relabels ACD/BC as annotation-defect probes, and
adds tests that pin the strict truth tables, source-file hashes, failed-answer sets, and
candidate evidence class.

### Prevention

Before promoting a source answer, search for and reconcile every later versioned source
audit for the same qid. Candidate files and the evidence class supporting them must be
tested separately so a valid experimental CSV cannot inherit an invalid truth claim.

### Metadata

- Reproducible: yes
- Related Files: `evaluation_results_v100/annotation_defect_pair_audit_v1.json`
- Related Files: `evaluation_results_v109/sentinel_calibrated_six_chance_plan_audit_v1.json`
- Related Files: `evaluation_results_v110/source_range_conditional_clause_correction_audit_v1.json`
