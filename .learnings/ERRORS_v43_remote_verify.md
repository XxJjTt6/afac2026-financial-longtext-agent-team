# V43 Remote Verification Error

## ERR-20260712-V43-ZSH-PATH

**Logged**: 2026-07-12T21:45:00+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary

在 zsh 的远端字节校验循环中使用变量名 `path`，覆盖了 zsh 与 `PATH` 绑定的特殊
数组，导致循环体内的 `git`、`shasum` 和 `awk` 都变成 command not found。

### Suggested Fix

zsh 脚本中不要把 `path` 用作普通循环变量；统一使用 `file_path`。修正变量名后，
同一校验命令通过，本地与 GitHub 提交及关键文件字节一致。
