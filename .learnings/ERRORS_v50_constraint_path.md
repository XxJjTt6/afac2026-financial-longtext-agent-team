# V50 Constraint Audit Errors

## [ERR-20260712-V50-001] relative Path parent does not move to dataset root

**Logged**: 2026-07-12T23:08:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

在内联 Python 中使用 `Path('.').parent` 仍得到当前相对目录，导致题库未加载并在
约束枚举时出现 `KeyError`。

### Error

```text
KeyError: 'fc_a_001'
```

### Suggested Fix

约束脚本统一使用 `Path.cwd().resolve()` 后再取 `.parent`。

---
