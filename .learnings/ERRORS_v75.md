# V75 Errors

## ERR-20260714-V75-001 derived_anchor_presented_as_observed_incumbent

**Status**: resolved

`fc_a_015=A` 在近期题型感知官网约束下确实被唯一确定，但对应的 94 题文件没有被
单独上传。此前多轮把这个未提交反事实简称为“当前可靠 94 题锚点”，没有始终同时
标明官网实测最佳仍是 93，导致条件 97 投影看起来像建立在实测 94 上。V75 起强制
分离 `best_observed_correct=93` 与 `derived_unsubmitted_anchor=94`。

## ERR-20260714-V75-002 promoted_change_calibration_collapse

**Status**: route retired

V36 后首次提交的 16 个不同候选答案只有 1 个正确，15 个错误；贡献分解为 1 个
正向、12 个负向、3 个中性。此前仍使用同一 Qwen 的重复一致和条件代数推动批量
提交，没有用这组“被选择残差上的真实增益率”否决路线。V75 退役模型单独分歧批次、
同模型票数放大和无独立绑定的条件高分路线。
