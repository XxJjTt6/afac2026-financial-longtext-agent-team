# V26 Errors - Follow-up

## ERR-20260712-002 full100_qwen_rate_limit

**Logged**: 2026-07-12T14:04:00+08:00
**Priority**: high
**Status**: resolved-by-route-change
**Area**: infra

### Summary

把累计请求配额提升到 1000 后，全量并发复核仍因 Coding API 的 HTTP 429 中止；旧全量脚本在异常前不保存已完成题目。

### Error

```text
429 Client Error: Too Many Requests
```

### Root Cause

`03_run_questions.py` 同时并发多道题，而每道多选题内部还会并发逐选项调用。进程内信号量无法协调另一个同时运行的高思考审计进程，合计请求突发超过接口速率限制。脚本又在所有 future 完成后才统一写盘，因此单个 429 会使整轮没有可恢复检查点。

### Resolution

不再用该脚本做本轮 100 题高并发复核。后续改为小规模残差池、单进程低并发、每组独立输出；官网硬约束已提供比全量模型重跑更强的两道唯一标签证据。

### Metadata

- Reproducible: yes
- Related Files: `scripts/03_run_questions.py`, `agent/reasoning/solver.py`, `agent/runtime/parallel.py`
- See Also: `ERRORS_v26.md`

---
