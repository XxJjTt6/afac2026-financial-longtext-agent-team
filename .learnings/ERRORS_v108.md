# Errors V108

## ERR-20260718-108-001 direct-script-import

**Priority**: low

### Summary

直接执行 V108 构建脚本时，项目根目录未进入 `sys.path`。

### Error

```text
ModuleNotFoundError: No module named 'agent_team_v108'
```

### Context

命令为 `.venv/bin/python scripts/133_build_v108_scorer_neutrality_stationarity_v1.py`。
同仓库既有构建脚本在导入项目包之前显式加入仓库根目录，V108 初稿遗漏了该步骤。

### Suggested Fix

在项目包导入前执行 `sys.path.insert(0, str(ROOT))`。修正后重新运行构建脚本和定向
测试。

### Metadata

- Reproducible: yes
- Related Files: `scripts/133_build_v108_scorer_neutrality_stationarity_v1.py`

---

## ERR-20260718-108-002 git-diff-check

**Priority**: low

### Summary

首次暂存后 `git diff --cached --check` 检测到学习文档末尾多余空行。

### Error

```text
.learnings/LEARNINGS_v108.md:31: new blank line at EOF.
```

### Suggested Fix

删除文件末尾的额外空行，重新暂存并运行完整差异检查。

### Metadata

- Reproducible: yes
- Related Files: `.learnings/LEARNINGS_v108.md`

---
