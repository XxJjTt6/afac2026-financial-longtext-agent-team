# AFAC2026 赛题四：B 榜 V45 最高分版本

这是本项目 B 榜最高实测版本的发布快照。

## 官方结果

- 榜单：B 榜
- 提交时间：2026-07-25 16:48:08
- 官网成绩：92.3949
- 前一条已知成绩：91.3741
- 版本：B 榜 V45（未舍入财务修正）
- 在线 Token：498,816（低于 500,000 限制）
- 唯一答案修正：`fin_b_014: 8.70 -> 8.69`

## 目录

- `agent/`：通用数据结构、提交格式和运行支持
- `agent_team_b1/`：B 榜 V45 计算与提交构建代码
- `evaluation_results_b1_v42_raw_pdf_accuracy_recovery/`：V45 的完整基线答案行
- `evaluation_results_b1_v45_fin14_unrounded/`：V45 修正行与提交清单
- `submissions/`：B 榜 V45 最终提交 CSV
- `upload_b/submit.csv`：官方 B 榜题目模板
- `tests/`：V45 计算和提交回归测试

## 复核

```bash
python -m pytest -q tests/test_b1_financial_unrounded_v45.py tests/test_b1_submission_v45.py
```

V45 只替换 `fin_b_014` 的未舍入差值；提交文件的 Token、题目数量和答案格式均由代码校验。
