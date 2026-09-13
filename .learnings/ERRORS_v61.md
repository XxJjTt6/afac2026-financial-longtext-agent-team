# V61 Errors

## ERR-20260713-V61-001 pytest_path

**Logged**: 2026-07-13T10:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

系统 PATH 中没有 `pytest`。改用仓库固定环境 `.venv/bin/python -m pytest`，并重新执行红绿测试。

## ERR-20260713-V61-002 relative_dataset_root

**Logged**: 2026-07-13T10:05:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

一次性约束审计把 `Path('.')` 的相对父目录误当作数据集根目录，导致 qid 查找失败。改用 `Path('.').resolve()` 后重跑。

## ERR-20260713-V61-003 submission_summary_in_registry

**Logged**: 2026-07-13T10:15:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: config

注册表直接把提交 CSV 的 `answer` 列作为答案矩阵时把 summary 行计为第 101 题。改为生成不含 summary 的 V61 独立矩阵，再进行哈希绑定。

## ERR-20260713-V61-004 v23_v27_attribution_conflation

**Logged**: 2026-07-13T10:25:00+08:00
**Priority**: high
**Status**: resolved
**Area**: evaluation

初始归因错误地把 V27 到 V36 的五处变化写成 V23 到 V36；实际 V23 到 V36 有八处变化。已删除监管双题精确净贡献断言，改为枚举所有保留近期直接提交的最小旧列隔离方案，并只推广结论交集。

## ERR-20260713-V61-005 unprotected_recent_runs

**Logged**: 2026-07-13T10:35:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: evaluation

首次枚举单列隔离时把近期直接提交也当成可删除对象。现已固定保护 V23、V36、V51、V58、V60，只在旧重建列中寻找最小修复。
