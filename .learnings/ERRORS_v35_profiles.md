# V35 Profile Error

## [ERR-20260712-V35-001] residual-profile-parent-key

**Logged**: 2026-07-12T17:35:00+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary

首版候选配置误用 `inherits`，而项目解析器只识别单父级字段 `extends`，导致目标候选漏掉父配置的两项修复。

### Resolution

在提交前把同一未发布配置更正为 `extends: core94`，重新生成目标CSV并由差分测试验证五项变化完整存在。错误CSV未进入Git历史或正式交付。

---
