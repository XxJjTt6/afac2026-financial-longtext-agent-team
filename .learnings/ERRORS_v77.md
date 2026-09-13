# V77 Errors

## [ERR-20260714-V77-001] GitHub 环境 Token 覆盖了本地登录

**Status**: resolved

V76 首次 `git push` 时，当前 shell 中的 `GITHUB_TOKEN` 覆盖了 `gh` keyring 里的有效登录，
导致 GitHub 拒绝认证。使用以下方式后推送成功：

```bash
env -u GITHUB_TOKEN git push -u origin <branch>
```

不记录任何 Token 值。
