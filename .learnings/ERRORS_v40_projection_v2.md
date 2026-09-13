# V40 Projection Correction

- The first projection test incorrectly treated a single successful new label
  as `98/100` for a candidate that changes both labels.
- Correct delta accounting is relative to V38: a true new label contributes
  `+1`, a true old label contributes `-1`, and an unobserved third label is
  neutral because both old and new submissions miss it.
- Therefore the two-candidate old/new scenarios are `99`, `97`, and `95`, not
  `99`, `98`, and `97`. V3 records the full old/new/other ladder.
