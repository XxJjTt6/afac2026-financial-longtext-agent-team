# V34 Command Errors

## [ERR-20260712-CMD-V34-001] pytest-not-on-global-path

**Logged**: 2026-07-12T17:10:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

直接执行 `pytest` 时全局环境没有该命令；项目依赖安装在仓库虚拟环境中。

### Resolution

改用仓库绝对路径 `.venv/bin/pytest`，避免依赖当前 shell 的 PATH。

### Metadata

- Reproducible: yes
- Related Files: `tests/test_v34_qwen37max_stable_jury.py`

---
