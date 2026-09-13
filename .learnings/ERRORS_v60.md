# V60 Errors

## ERR-20260713-V60-001 script_import_path

**Logged**: 2026-07-13T03:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: tooling

### Summary

V60 builder initially failed before artifact generation because the standalone script imported
the project package before adding the repository root to `sys.path`.

### Error

```text
ModuleNotFoundError: No module named 'agent'
```

### Resolution

Define `ROOT`, insert it into `sys.path`, and only then import project modules. The subsequent
run and artifact tests must pass before promotion.

### Metadata

- Reproducible: yes
- Related Files: scripts/90_build_v60_fc4_confirmation_frontier_v1.py
- Secret Data: none
