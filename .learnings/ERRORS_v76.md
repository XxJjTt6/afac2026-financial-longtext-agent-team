# V76 Errors

## [ERR-20260714-V76-001] 前端资源搜索引号错误

**Status**: resolved

第一次在 zsh 中组合 `curl` 与包含引号的正则表达式时出现 `unmatched "`。改为可验证的
双引号正则后恢复，不影响任何产物。

## [ERR-20260714-V76-002] 直接打开成绩 API 被浏览器拦截

**Status**: resolved

已登录 Chrome 中直接打开 `/race/score/my` GET 地址被客户端拦截，受限的页面读取上下文也不提供
`fetch`。不继续猜测认证参数，改为通过可见的“提交结果”页面读取服务器文件名和时间。

## [ERR-20260714-V76-003] 冲突修复字段名预期错误

**Status**: resolved

V76 构建器首次把 V74 中的 `reported_correct` 误写为 `original_correct`，导致构建门禁正确拒绝。
读取真实 V74 产物后修正字段名并重跑成功。
