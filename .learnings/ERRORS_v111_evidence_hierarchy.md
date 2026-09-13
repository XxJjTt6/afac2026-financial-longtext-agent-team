# V111 Evidence Hierarchy Error

## ERR-20260718-111

**Priority**: critical

**Status**: resolved

### Summary

V109/V110 将原文语义排在精确官网分数方程之上，退役了联合方程支持的 `reg_a_004=ABC`，并优先提交了后来被新精确分数行排除的 `fc_a_004=ACD`。

### Root Cause

- 把“原文正确答案”错当成“隐藏评分键”。
- 没有坚持 `v58` 是唯一最小不一致绑定的结论。
- 候选排序没有在新外部精确分数行进入后重新求解。

### Resolution

- V111 隔离 `v58`，内部方程唯一强制 `fc_a_015=C`。
- 加入两个公开仓库的六个完整精确分数行，定位 V85 五道错题并唯一强制 `reg_a_004=ABC`。
- 退役重复 95 题控制和 `fc_a_004=ACD` 路线，改为先单题验证 fc15，再叠加 reg4。

### Related Files

- `evaluation_results_v111/official_ledger_external_calibration_audit_v1.json`
- `docs/team/2026-07-18-V111官网账本修复与外部精确分数联合定位_v1.md`
