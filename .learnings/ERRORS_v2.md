# Errors V2

Command failures and integration errors captured during V12.

---

## [ERR-20260712-001] V12 dry-run index path

**Logged**: 2026-07-12T05:56:00+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
首次 V12 dry-run 未显式指定现有 V1 索引目录，Settings 使用了空的默认目录。

### Error
`FileNotFoundError: processed_data/indexes/bm25_index.pkl`

### Suggested Fix
复现实验显式设置 `AFAC_INDEX_DIR=processed_data_v1/indexes`。

---

## [ERR-20260712-002] security scan shell quoting

**Logged**: 2026-07-12T06:13:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
首版组合扫描命令在单引号正则中再次嵌入引号，导致 zsh 解析失败。

### Error
`zsh: parse error near ')'`

### Suggested Fix
把扫描拆为两个不含嵌套引号的 `rg` 命令；修正版已通过。

---

## [ERR-20260712-003] optional retrieval artifact test mismatch

**Logged**: 2026-07-12T06:18:00+08:00
**Priority**: medium
**Status**: investigated
**Area**: tests

### Summary
显式加载 `processed_data_v1/indexes` 后，一项既有财报文档级探针失败；V12 未修改
相关索引、检索实现或测试。

### Error
`annual_chinamobile_2025_report` 排在 `annual_byd_2025_report` 之前，违反该探针
要求比亚迪文档第一的断言。

### Context
- 多个 `PYTHONHASHSEED` 均可复现，排除哈希随机性。
- 不指定可选索引产物时，完整默认测试为 `377 passed, 13 skipped`。
- V12 定向测试连同 V11 实体绑定测试为 `9 passed`。
- 这是既有索引产物与集成探针的兼容问题，不在 V12 分支修改范围内。

### Suggested Fix
后续单独在新分支比较 `processed_data_v1/indexes` 的构建配置与该探针预期，不在
实体绑定分支改写通用检索排序。

---
