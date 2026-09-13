# V33 命令与运行错误

## [ERR-20260712-CMD-V33-001] wrong-runtime-paths

**Logged**: 2026-07-12T15:45:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary

首次运行文档级验证器时沿用了仓库默认数据路径，导致全部题号被报告为未知。

### Error

```text
KeyError: Unknown qids
```

### Resolution

运行时显式设置 `AFAC_QUESTIONS_ROOT` 与 `AFAC_PROCESSED_DIR` 指向当前外部官方数据和 `processed_data_v1`，不修改历史配置文件。

---

## [ERR-20260712-CMD-V33-002] cumulative-request-quota

**Logged**: 2026-07-12T15:58:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary

误把 `AFAC_QWEN_REQUEST_LIMIT` 当成并发数设为6；该值实际是进程累计请求配额，第七次请求触发配额错误。

### Error

```text
RuntimeError: quota exceeded for qwen: 6/6
```

### Resolution

将累计请求配额恢复为100，并用 `AFAC_QWEN_WORKERS=4` 单独控制并发；通过 `--resume` 保留前六题结果后完成74题审计。

---

## [ERR-20260712-CMD-V33-003] relative-venv-path

**Logged**: 2026-07-12T15:35:00+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary

在工作区上级目录调用 `.venv/bin/python`，相对路径不存在。

### Resolution

后续从仓库根目录运行，或使用仓库虚拟环境的绝对路径。

---
