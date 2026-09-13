# V36 Remote Verification Error

## [ERR-20260712-V36-001] ls-remote-invalid-env-token

**Logged**: 2026-07-12T17:42:00+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary

普通 `git ls-remote` 再次被环境中的无效 `GITHUB_TOKEN` 覆盖，尽管使用GitHub CLI凭据的正式推送已经成功。

### Resolution

远端验证与推送统一清除该环境变量，并显式使用GitHub CLI credential helper；不输出或保存任何令牌。

---
