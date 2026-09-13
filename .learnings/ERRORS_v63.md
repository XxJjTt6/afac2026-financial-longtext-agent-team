# V63 Errors

## ERR-20260713-V63-001 selected_registry_overpromotion

**Logged**: 2026-07-13T17:00:00+08:00
**Priority**: critical
**Status**: resolved
**Area**: evaluation

### Summary

V62 把四个同为最小基数的旧注册表修复之一提升为 96-97 条件主分支，并用于今天最后一次提交；官网返回最差边界 91 题。

### Root Cause

编码矩阵可逆，但候选选择没有足够证据。隔离 v12 与隔离 v4、v5、v11 在数学上同阶，且直接语义证据支持 V36 的 res17/res18 答案。V62 把“失败后可解码”误当成“提交前置信度较高”。

### Resolution

P1 极端反馈已严格确认三个 V36 旧答案正确。V63 退役 P2/P3，建立近期直接快照注册表，并禁止旧重建列继续产生硬标签。

### Metadata

- Reproducible: yes
- Related Files: `submissions/v62_p1_dense_abc_from_v36_answer.csv`, `evaluation_results_v63/p1_official_attribution_v1.json`
- Secret Data: none

## ERR-20260713-V63-002 csv_verification_field_name

**Logged**: 2026-07-13T17:10:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

V63 临时验证脚本把提交文件的 Token 汇总列误写成 `tokens`，实际列名为
`total_tokens`，导致 `KeyError`。

### Root Cause

验证脚本未先读取 CSV 表头，使用了错误字段名；生成器和提交文件本身没有异常。

### Resolution

先检查表头，再以 `total_tokens` 执行 100 题、唯一 qid、Token 和单点差异验证。

### Metadata

- Reproducible: yes
- Related Files: `submissions/v63_fc15_only_recovery_anchor_answer.csv`
- Secret Data: none
