# V40 Builder Import Error

- Direct execution of `scripts/67_build_v40_conditional99_candidate.py`
  failed with `ModuleNotFoundError: No module named 'agent'`.
- Root cause: direct script execution places `scripts/`, not the repository
  root, at `sys.path[0]`.
- The repository's working builder pattern inserts `ROOT` before importing
  project modules. V2 follows that established pattern and leaves V1 as the
  recorded failed attempt.
