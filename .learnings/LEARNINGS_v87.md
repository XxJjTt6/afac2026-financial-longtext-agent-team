# LEARNINGS V87

1. V68 must be compared with the observed V80=93 row, not the falsified derived 94 anchor. The localized delta is `-1`, not `-2`.
2. V80 differs from V36 only at `fc_a_015: B->A` and has the same 93 correct, so that cell contributes zero under the user-attested binding.
3. V68 differs from V80 only at `ins_a_006`, `reg_a_004`, and `reg_a_017`. Source text fixes the first two incumbent answers as `A` and `C`, so their changes to `C` and `ABC` each contribute `-1`.
4. The trio total is `-1`; therefore `reg_a_017: ABC->AB` must contribute `+1` under those source labels. This rescues a candidate previously retired by the bad anchor arithmetic.
5. The blind V77 source audit independently answered `reg_a_017=AB`; the non-blind audit's `ABC` reversal used the leaked historical constraint and is not independent.
6. The V85/fgrt equation closes as 13 V85 wins, 2 fgrt wins, and 0 both-wrong cells only when `ins_a_014=AB` stays unchanged. V86's third change to `A` should therefore be retired.
7. Weighted public-row optimization can return one convenient feasible gold assignment without forcing those labels. Never report an objective-selected solution as a constraint-forced identity.
