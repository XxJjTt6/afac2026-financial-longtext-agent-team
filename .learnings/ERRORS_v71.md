# V71 Errors

## ERR-20260714-V71-001 wrong_script_number

**Logged**: 2026-07-14T03:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary

首次读取 V64 构建器时误写为 `scripts/96_build...`，实际文件为
`scripts/94_build_v64_recent_residual_frontier_v1.py`。

### Resolution

后续先用 `rg --files scripts | sort -V` 确认编号，不再猜测脚本序号。

---

## ERR-20260714-V71-002 unavailable_python_alias

**Logged**: 2026-07-14T03:10:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary

公开矩阵临时分析首次调用 `python`，当前环境只有 `python3` 与项目 `.venv/bin/python`。

### Resolution

非项目依赖分析使用 `python3`，导入项目模块时固定使用 `.venv/bin/python`。

---

## ERR-20260714-V71-003 relative_question_root

**Logged**: 2026-07-14T04:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: evaluation

### Summary

探索性约束脚本用 `Path('.').parent` 计算题目目录，结果仍指向当前目录并导致合法答案表为空。

### Resolution

改用 `Path.cwd()` 后再取父目录，近期运行、V68、公开 V43 与 12 项标签约束联合可行。
