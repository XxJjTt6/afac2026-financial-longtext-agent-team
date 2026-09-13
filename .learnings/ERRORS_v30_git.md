# V30 Git 推送错误

## ERR-20260712-002 无效环境令牌覆盖有效钥匙串登录

- 时间：2026-07-12
- 现象：普通 `git push` 返回 GitHub 鉴权失败。
- 根因：当前进程中的 `GITHUB_TOKEN` 已失效，并覆盖了 macOS 钥匙串中仍有效的 GitHub CLI 登录。
- 最小验证：移除该环境变量后，`gh auth status` 与远端只读访问均成功。
- 处理：仅在本次 Git 命令中清除失效环境令牌，并显式使用 GitHub CLI credential helper；未打印、写入或提交任何令牌。
- 结果：`experiment/v30-fc004-complete-source-audit` 已成功推送。

