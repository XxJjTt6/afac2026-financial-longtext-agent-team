# V61 Push Error V1

## ERR-20260713-V61-006 invalid_github_token_override

**Logged**: 2026-07-13T10:50:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

首次推送时，环境中的失效 `GITHUB_TOKEN` 覆盖了 macOS keyring 中仍有效的 GitHub CLI 凭据，HTTPS 鉴权失败。使用 `env -u GITHUB_TOKEN git push` 后改由 keyring 凭据完成推送；未记录任何令牌内容。
