# Learnings V108

## LRN-20260718-108-001 correction

**Priority**: critical

### Summary

穷尽全部合法答案且得分相同时，不能把该题直接建模为“恒错”。

### Details

`fc_a_015` 的 A/B/C/D 四个合法单选输出在登记的隔离文件中都得到 93 题。旧的
`NO_MATCH` 状态只表达常数贡献 0，却遗漏常数贡献 1、题目不计分、绑定失效和跨时点
评分变化。由这个不完备状态推导出的 V85 恰有两个残差错误和 V106 四个穷尽模式都
不是服务器事实。

### Suggested Action

任何跨提交方程都先检查评分时序、账号、文件路径、总 Token、最新结果时间和服务器
摘要。答案不敏感题必须保留常数贡献 0/1 两个分支；缺少服务器摘要时，使用同日基线
控制后再做单题探针。

### Metadata

- Source: root-cause audit
- Related Files: `agent_team_v108/scorer_neutrality_stationarity_v1.py`
- Tags: scorer-stationarity, result-binding, open-world, leaderboard

---
