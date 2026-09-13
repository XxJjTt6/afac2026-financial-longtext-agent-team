# V33 API 路由记录

## [ERR-20260712-API-V33] coding-endpoint-authentication

**Logged**: 2026-07-12T15:42:00+08:00
**Priority**: high
**Status**: resolved-with-approved-qwen-route
**Area**: infra

### Summary

两个 Coding Plan 兼容接口均返回 HTTP 401，但本机已有的另一份 DashScope 凭据可正常访问百炼标准 OpenAI 兼容接口，并提供 `qwen3.7-plus` 与 `qwen3.7-max`。

### Error

```text
coding.dashscope.aliyuncs.com/v1/chat/completions -> HTTP 401
coding.dashscope.aliyuncs.com/apps/anthropic/v1/messages -> HTTP 401
```

### Resolution

改用 `https://dashscope.aliyuncs.com/compatible-mode/v1`，`GET /models` 返回 HTTP 200；随后 `qwen3.7-plus` 正式审计成功。全过程未输出、保存或提交任何凭据。

### Metadata

- Reproducible: yes
- Related Files: `agent/llm/qwen_client.py`
- Security: no secret values recorded

---
