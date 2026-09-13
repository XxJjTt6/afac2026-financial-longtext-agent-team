# V27 Learnings

## LRN-20260712-001 best_practice

**Logged**: 2026-07-12T14:20:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary

排行榜稳定题池大小必须从答案矩阵程序化计算，不能根据变更清单心算。

### Details

初稿把 V4-V23 从未变化的题数写成 77；新增测试从 100 行矩阵逐行计算后得到 74。26 道历史变更题中当前有 5 道错误，因此 89/100 基线的另外 6 道错误恰好位于 74 道稳定题中。

### Suggested Action

文档中的集合大小和剩余错误数继续由测试从受哈希保护的矩阵派生，不手工维护重复数字。

### Metadata

- Source: test_failure
- Related Files: `tests/test_v27_reg004_candidate.py`, `configs/v27_pseudogold_ledger.json`
- Tags: leaderboard, constraint, derived-count

---
