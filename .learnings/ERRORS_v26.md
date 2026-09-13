# V26 Errors

## ERR-20260712-001 full100_qwen_quota

**Logged**: 2026-07-12T14:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary

全量 100 题独立复核在第 101 次 Qwen 请求前被本地累计配额中止，且旧脚本只在全部任务结束后写盘，已完成结果没有形成检查点。

### Error

```text
RuntimeError: quota exceeded for qwen: 100/100
```

### Root Cause

运行命令把 `AFAC_QWEN_REQUEST_LIMIT` 误设为 100；该参数是一次进程内的累计请求上限，不是并发数。多选题逐选项判定会让 100 道题产生超过 100 次调用。

### Resolution

失败目录保留为负向记录；重跑时使用运行时配置的 1000 次配额，并写入新的 V2 输出目录，避免覆盖失败现场。

### Metadata

- Reproducible: yes
- Related Files: `agent/runtime/parallel.py`, `scripts/03_run_questions.py`

---
