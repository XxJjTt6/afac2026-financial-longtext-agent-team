# V65 Errors

## ERR-20260713-V65-001 stale_process_api_key

**Logged**: 2026-07-13T19:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: integration

### Summary

V65 首次调用被进程环境中旧的 `DASHSCOPE_API_KEY` 抢占本地私有配置，兼容接口返回 401。

### Root Cause

`get_api_key()` 优先读取进程环境变量，而有效凭据位于被 Git 忽略的本地配置中；两者长度和内容不同。

### Resolution

正式重跑时只从当前进程移除旧的同名环境变量，让既有本地私有配置生效。22 次正式 Qwen 调用全部完成，未在命令、日志或产物中写入密钥。
