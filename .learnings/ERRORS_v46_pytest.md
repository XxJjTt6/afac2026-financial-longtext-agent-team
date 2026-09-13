# V46 Errors

## [ERR-20260712-V46-001] pytest executable path

**Logged**: 2026-07-12T22:16:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

直接调用 `pytest` 时当前非交互 shell 的 `PATH` 未包含项目虚拟环境。

### Error

```text
zsh: command not found: pytest
```

### Suggested Fix

本仓库测试统一显式调用 `.venv/bin/pytest`，Python 校验统一调用 `.venv/bin/python`。

---
