# Errors

Command failures and integration errors.

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

### Context
- 新实验从仓库根目录执行，真实索引保存在 `processed_data_v1/indexes`。
- 不涉及模型调用或密钥。

### Suggested Fix
所有复现实验显式设置 `AFAC_INDEX_DIR=processed_data_v1/indexes`，并在脚本参数与清单中记录解析后的索引路径。

### Metadata
- Reproducible: yes
- Related Files: agent/config.py, agent_team_v12/entity_bound_runtime.py

---
