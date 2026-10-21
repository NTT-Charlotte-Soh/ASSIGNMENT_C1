# aXet Code — Persistent Agent Instructions for Logscope

This file contains standing instructions for all future aXet Code sessions working on the `logscope` project.
Read and follow every rule below before making any change.

---

## 1. Architecture Expectations

- `logscope` is a Python package installable via `pip install -e .`.
- Entry point: `logscope` CLI command, defined in `pyproject.toml` console_scripts.
- All log processing **must be streaming (line-by-line)**. Never load an entire file into memory.
- Package layout is defined in `SPEC.md` Section 9. Do not deviate without updating SPEC.md.
- No third-party runtime dependencies. Use Python stdlib only.
- `pytest` is the only allowed dev dependency.

### Module responsibilities

| Module | Responsibility |
|--------|---------------|
| `logscope/parser.py` | Streaming line-by-line log parser; returns structured records; counts malformed lines |
| `logscope/cli.py` | argparse CLI definition; dispatches to commands |
| `logscope/commands/summary.py` | Summary command logic |
| `logscope/commands/timeline.py` | Timeline command logic |
| `logscope/commands/grep.py` | Grep command logic |
| `logscope/output/text.py` | Human-readable text formatters |
| `logscope/output/json_fmt.py` | JSON output formatter |
| `logscope/output/markdown.py` | Markdown report writer |

---

## 2. Test Commands

Always run tests from the repo root:

```bash
# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_parser.py -v

# Run with coverage (optional)
pytest tests/ --tb=short
```

Tests must pass before committing any stage.

---

## 3. Streaming Requirement

**Critical:** The parser must process files line by line using a `for line in file_handle:` loop.
Never use `file.read()`, `file.readlines()`, or load the full file into a list.
This ensures stable/bounded memory on 100 MB+ files.

---

## 4. Quality Rules

- All functions must have docstrings.
- Malformed lines must never cause an exception — wrap parsing in try/except and increment `malformed_count`.
- All output to users goes to **stdout**. Warnings/diagnostics go to **stderr**.
- Exit codes must match SPEC.md Section 2 exactly.
- Markdown filenames follow the convention in SPEC.md Section 4.2. Never silently overwrite.
- Timestamp format: `YYYY-MM-DD HH:MM:SS`, assumed UTC. Documented in SPEC.md Section 1.

---

## 5. Git Commit and Push Rules

Every stage must be committed and pushed individually:

```bash
# After completing a stage:
git add <relevant files>
git diff --cached   # inspect staged changes
git commit -m "<exact message from task>"
git push origin main
```

**Commit messages must match the task specification exactly.**

### STOP-ON-FAILURE rule

If `git commit` or `git push` fails for any reason:
1. **STOP IMMEDIATELY.** Do not proceed to the next stage.
2. Report:
   - The stage that failed
   - The exact command that failed
   - The complete error output
   - The action needed to unblock progress

Never force-push, amend commits, rebase, or rewrite Git history.

---

## 6. What Never to Commit

Never commit:
- Secrets, tokens, API keys, private SSH keys
- `.env` files
- Generated large log files (e.g., 100 MB benchmark logs) — these must be in `.gitignore`
- Python caches: `__pycache__/`, `*.pyc`, `*.pyo`
- Virtual environments: `venv/`, `.venv/`, `env/`
- Build artefacts: `dist/`, `build/`, `*.egg-info/`
- Editor/IDE files: `.vscode/settings.json` (unless project-wide)

---

## 7. Stage Completion Checklist

After completing each stage, verify and report:

- [ ] All tests pass (`pytest tests/ -v`)
- [ ] `git diff` and `git status` inspected
- [ ] Commit created with exact message from task
- [ ] Push to `origin main` succeeded
- [ ] Commit hash recorded

---

## 8. Performance Baseline

A 100 MB log must be processed by each required command in under 60 seconds.
Memory must remain stable (not grow proportionally with file size).
Benchmark must be **run** and **measured**, not assumed. Document results in `PLAN.md` after Stage 8.

---

## 9. Log Format Reference

```
YYYY-MM-DD HH:MM:SS LEVEL message text here
```

- Timestamps assumed UTC
- Levels: `INFO`, `WARN`, `ERROR`, `DEBUG` (others are valid)
- Malformed = no parseable timestamp OR fewer than 3 tokens

See `SPEC.md` for full details.

---

## 10. SSH / Git in WSL

- Git commands must be run via WSL: `wsl -e bash -c "cd /mnt/c/... && git ..."`
- SSH key for GitHub is configured in WSL; do not change remote to HTTPS
- Remote must always be: `git@github.com:NTT-Charlotte-Soh/ASSIGNMENT_C1.git`
- Verify SSH auth before pushing: `ssh -T git@github.com`
