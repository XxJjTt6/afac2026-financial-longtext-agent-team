# V72 Errors

## ERR-20260714-V72-001 gh_api_query_globbing

**Logged**: 2026-07-14T05:10:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary

首次查询 GitHub issues 和用户仓库列表时未给带 `?` 的 API 路径加引号，zsh 将其
解释为文件通配符并报 `no matches found`。

### Resolution

所有包含查询参数的 `gh api` 路径使用单引号包围；复查确认外部仓库没有公开 issue、
release 或 Actions artifact，用户另有 8 个公开仓库但没有 AFAC 赛题四成绩附件。
