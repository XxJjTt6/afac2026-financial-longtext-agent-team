# V27 Pair Audit Error

## ERR-20260712-003 fc12_fc15_high_timeout

**Logged**: 2026-07-12T14:27:00+08:00
**Priority**: medium
**Status**: closed-without-rerun
**Area**: infra

### Summary

`fc_a_012/fc_a_015` 五路高思考标签冲突审计连续三次在 120 秒读取超时后中止，未形成完整可比较结果。

### Error

```text
ReadTimeout: coding.dashscope.aliyuncs.com read timeout=120
```

### Context

全量低并发单轮审计已经完成，但随后高思考请求出现长时间服务端无响应。并发 future 中任一异常会阻止聚合文件写出，因此本轮没有把不完整内存结果当作证据。

### Resolution

不重跑，不基于缺失票数修改 `fc_a_012/fc_a_015`。两题继续只保留“当前答案恰有一个命中”的官网集合约束；V27 提交不触碰它们。

### Metadata

- Reproducible: unknown
- Related Files: `configs/v27_pseudogold_ledger.json`
- See Also: `.learnings/ERRORS_v26_2.md`

---
