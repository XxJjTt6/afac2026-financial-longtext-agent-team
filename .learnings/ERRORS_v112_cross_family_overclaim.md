# V112 Cross-Family Overclaim

## ERR-20260718-112

**Priority**: critical

**Status**: resolved

## Summary

V111 将 5 条 `usercjr` 历史行和 1 条 `xuxu` 行联立得到的
`reg_a_004=ABC` 表述为所有外部精确分数行的联合精确答案。
新增 Kafka V2 后，外部行整体不可行，且 Kafka+xuxu 家族反而强制
`reg_a_004=C`。

## Root Cause

- 把同一团队的多个版本当作多个独立证据源。
- 在新的独立公开行进入后，没有先按证据家族分层检查可行性。
- 将“单一可行模型中强制”写成了“跨可行模型强制”。

## Resolution

- 将公开行分为 `usercjr+xuxu` 和 `Kafka+xuxu` 两个互斥家族模型。
- 只保留两个家族共同强制的 `fc_a_015=C` 作为 P1。
- 将 `reg_a_004=ABC` 降级为仅在 P1=96 后使用的家族辨别探针。
- 后续候选全部改为从已确认 96 题 P1 锨点出发的单题隔离文件。

## Related Files

- `evaluation_results_v112/cross_family_six_slot_audit_v1.json`
- `evaluation_data/external/v112_kafka_provenance_registry_v1.json`
- `docs/team/2026-07-18-V112跨公开分数家族冲突与六次单题提交树_v1.md`
