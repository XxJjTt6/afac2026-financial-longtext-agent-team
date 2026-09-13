# Errors V3

## [ERR-20260712-001] full_pytest_index_override

**Logged**: 2026-07-12T11:05:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary

全量测试命令给所有测试统一覆盖持久化索引路径，导致一个检索排序测试读取了错误的
外部索引并失败。

### Error

检索排序测试预期比亚迪年报第一，实际返回中国移动年报；428 项通过、1 项失败。

### Context

新增 V23 CLI 集成测试需要已有保险索引，但测试自身已经为子进程设置了该路径。首次
全量运行又在父进程全局重复设置，污染了依赖默认测试夹具的其他检索测试。

### Suggested Fix

需要特定持久化索引的集成测试应在自己的子进程环境内局部设置；全量回归只设置数据集
根目录，让其他测试继续使用各自夹具。按此方式重跑后全量通过。

### Metadata

- Reproducible: yes
- Related Files: tests/test_team_v23_multi_policy_contract.py
- Pattern-Key: tests.scope_external_index_override

### Resolution

- **Resolved**: 2026-07-12T11:07:00+08:00
- **Notes**: 去除父进程的全局索引覆盖后重跑，419 passed、13 skipped。

---
