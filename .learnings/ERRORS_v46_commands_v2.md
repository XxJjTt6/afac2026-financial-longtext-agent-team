# V46 Command Errors V2

## [ERR-20260712-V46-002] zsh secret-scan quoting

**Logged**: 2026-07-12T22:21:00+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary

密钥扫描正则同时包含单双引号时，外层 shell 拼接产生未闭合引号。

### Error

```text
zsh: unmatched '
```

### Suggested Fix

拆成不含引号字符的两个简单正则扫描，避免在一条命令里混用多层 shell 引号。

---
