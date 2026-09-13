# V37 Attribution Errors

## [ERR-20260712-V37-001] default-question-root

**Logged**: 2026-07-12T18:20:00+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary

首轮定向验证沿用仓库内不存在的默认题目目录，17个题号全部报告为未知。

### Resolution

后续命令显式设置外部官方数据目录 `AFAC_QUESTIONS_ROOT`。失败发生在模型调用和文件写出之前。

---

## [ERR-20260712-V37-002] layout-index-rebuild-cost

**Logged**: 2026-07-12T18:32:00+08:00
**Priority**: medium
**Status**: resolved-by-route-change
**Area**: infra

### Summary

加载386MB版面索引时会重新构造多字段倒排表；运行超过12分钟、常驻内存接近4GB，仍未开始任何题目或API调用。

### Resolution

主动终止无信息增益的初始化，改用已经落盘的三轮Qwen证据快照构造定向陪审上下文。不得在最后一次提交前把昂贵初始化误当成新实验进展。

---

## [ERR-20260712-V37-003] stale-dashscope-environment-key

**Logged**: 2026-07-12T18:35:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary

本地优先级更高的 `DASHSCOPE_API_KEY` 指向失效凭据，Coding兼容接口返回HTTP 401。

### Resolution

仅在本次进程中移除失效变量，让客户端使用已经配置的有效兼容凭据；随后30次 `qwen3.7-plus` 定向陪审全部完成。未输出、记录或提交任何密钥值。

---
