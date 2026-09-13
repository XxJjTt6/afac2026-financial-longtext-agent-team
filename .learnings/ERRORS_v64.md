# V64 Errors

## ERR-20260713-V64-001 zsh_unmatched_glob

**Logged**: 2026-07-13T18:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: analysis

### Summary

使用 `evaluation_results_v56/*.json` 读取审计文件时，zsh 因目录下没有直接匹配文件而终止命令。

### Resolution

改用 `find ... -name '*.json' -print0` 枚举文件，避免 zsh 的 unmatched glob 行为。

## ERR-20260713-V64-002 misplaced_helper_function

**Logged**: 2026-07-13T18:15:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: analysis

### Summary

为 V64 builder 增加历史协议重合校准时，补丁把新函数插入 `_v23_relation` 中间，导致该函数隐式返回 `None`。

### Root Cause

补丁锚点只匹配了 `changed` 字典后的空行，没有核对函数剩余控制流。

### Resolution

恢复 `_v23_relation` 的完整计算和返回块，再把历史校准函数放到函数边界之后；聚焦测试恢复为 6/6 通过。
