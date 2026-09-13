# V44 Script Import Error

## ERR-20260712-V44-SYSPATH

**Logged**: 2026-07-12T22:20:00+08:00
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

直接执行 `scripts/75_build_v44_fc15_structural_forensics_v1.py` 时，Python 只把
`scripts/` 加入模块路径，无法导入仓库根目录的 `agent_team_v44`。

### Suggested Fix

与仓库既有脚本保持一致，在导入项目模块前把 `Path(__file__).parents[1]` 插入
`sys.path`。修正后重新执行真实构建命令，而不依赖 pytest 帮助配置的导入路径。
