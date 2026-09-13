# V39 Command Errors

## ERR-20260712-V39-001: Python executable name

- Command used `python`, but this workspace exposes Python as `python3` and `.venv/bin/python`.
- Error: `zsh: command not found: python`.
- Fix: use `.venv/bin/python` for repository experiments and `python3` for small read-only parsers.

## ERR-20260712-V39-002: Unmatched zsh glob

- A diagnostic command referenced a glob with no matching `reg_*.json` files.
- zsh aborted the command with `no matches found` before later diagnostics ran.
- Fix: use `find -name` or guard optional globs instead of relying on unmatched zsh patterns.

## ERR-20260712-V39-003: Long threaded API command outlived first tool yield

- Several threaded Qwen experiments continued after the first command wrapper returned its initial cell result.
- Fix: explicitly inspect the spawned `.venv/bin/python -` PID and wait until it exits before parsing results or ending the turn.
- No API key, credential value, or authorization header was logged.
