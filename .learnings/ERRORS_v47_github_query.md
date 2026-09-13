# V47 GitHub Query Errors

## [ERR-20260712-V47-001] zsh expands API query marker

**Logged**: 2026-07-12T22:31:00+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary

未引用的 GitHub API 路径含 `?per_page=20`，被 zsh 当作文件名通配符。

### Error

```text
zsh: no matches found: repos/.../commits?per_page=20
```

### Suggested Fix

所有含查询参数的 `gh api` 路径统一使用双引号。

---
