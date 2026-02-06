# Repository Guidelines

Tiger owns this. Session Start: say hi + 1 motivating line. 
Work style: telegraph; noun-phrases ok; drop grammar; min tokens.

- Session Start: run KB list; Open docs before coding.
- Need upstream file: stage in /tmp/, then cherry-pick; never overwrite tracked.
- Bugs: add regression test when it fits.
- Keep files <~500 LOC; split/refactor as needed.
- Prefer end-to-end verify; if blocked, say what’s missing.
- New deps: quick health check (recent releases/commits, adoption).
- Web: search early; quote exact errors; prefer 2024–2026 sources
- Style: telegraph. Drop filler/grammar. Min tokens.
- Delete unused or obsolete files (+folders) when your changes make them irrelevant (refactors, feature removals, etc.), and revert files only when the change is yours or explicitly requested. If a git operation leaves you unsure about other agents' in-flight work, stop and coordinate instead of deleting.
- Before attempting to delete a file to resolve a local type/lint failure, stop and ask the user. Other agents are often editing adjacent files; deleting their work to silence an error is never acceptable without explicit approval.
- NEVER edit .env or any environment variable files—only the user may change them.
- There may be multiple agents making edits
  - while you are working, if you notice such changes and they don't interfere (or don't look broken), no need to immediately ask the user how to proceed
  - when you are commiting, if they are in files you didn't touch, generally you should just exclude them from your commit
  - use your best judgement, if they are conflicting, interfere with your work, or look broken, stop and ask the user how to proceed
  - Coordinate with other agents before removing their in-progress edits—don't revert or delete work you didn't author unless everyone agrees.
- Moving/renaming and restoring files is allowed.
- ABSOLUTELY NEVER run destructive git operations (e.g., git reset --hard, rm, git checkout/git restore to an older commit) unless the user gives an explicit, written instruction in this conversation. Treat these commands as catastrophic; if you are even slightly unsure, stop and ask before touching them. (When working within Cursor or Codex Web, these git limitations do not apply; use the tooling's capabilities as needed.)
- Never use git restore (or similar commands) to revert files you didn't author—coordinate with other agents instead so their in-progress work stays intact.
- Always double-check git status before any commit
- Keep commits atomic: commit only the files you touched and list each path explicitly. For tracked files run git commit -m "<scoped message>" -- path/to/file1 path/to/file2. For brand-new files, use the one-liner git restore --staged :/ && git add "path/to/file1" "path/to/file2" && git commit -m "<scoped message>" -- path/to/file1 path/to/file2.
- Quote any git paths containing brackets or parentheses (e.g., src/app/[candidate]/**) when staging or committing so the shell does not treat them as globs or subshells.
- When running git rebase, avoid opening editors—export GIT_EDITOR=: and GIT_SEQUENCE_EDITOR=: (or pass --no-edit) so the default messages are used automatically.
- Never amend commits unless you have explicit written approval in the task thread.
- This codebase keeps a short `README.md` in each major directory. These files share a common structure so humans and LLMs can easily navigate the repository.
- As you plan and implement, run temporary tests scripts or test to validate code flows that you aren't 100% sure about.
- Run the available tests, linting, type checks (typescript) to validate your changes, expand the test suite as you go.
- When reviewing code, ask yourself "is this the best way to solve this?".

## Contributing

- Sync environment: `uv sync --locked`
- Run tests: `uv run pytest`
- Lint (with fixes): `uv run ruff check --fix .`
- Format: `uv run ruff format .`

## Dependency Workflow

`pyproject.toml` is the single source of truth.

- Add runtime dep: `uv add <package>`
- Add dev dep: `uv add --dev <package>`
- Remove dep: `uv remove <package>`
- Update lockfile: `uv lock`
- Upgrade dependencies: `uv lock --upgrade`

## Docs

Project docs and notes live in `docs/`. Keep high-level usage details in `README.md`.

## README Format

For major directories, keep a short local `README.md` with:

1. Directory title and short overview
2. `Contents` section with key files/subfolders and a short description

## Task Updates

When completing work, include a short summary of what changed and why, plus verification results.

# LLM Agent Knowledge Base

The `knowledge_base` folder is your knowledge base.

## Knowledge Base Metadata + Listing

Each KB article starts with YAML frontmatter:
```yaml
---
last_read: 2026-01-05T00:00:00Z
usefulness: 0
read_win_tags:
  - backend
  - fastapi
---

Rules

- Update last_read when you consult the doc.
- Bump usefulness +1 when it helps; -1 when it misleads.
- Keep read_win_tags small, concrete, lowercase.

Listing script

- List all, sorted by tag match → usefulness → last_read:

  python3 knowledge_base/list_kb.py
- Filter by tag:

  python3 knowledge_base/list_kb.py --tags backend --show-meta
- Require all tags:

  python3 knowledge_base/list_kb.py --tags backend,fastapi --require-all --show-meta

Notes

- Frontmatter must be the first block in the file.
- Use ISO-8601 timestamps (UTC Z preferred).
- Any missing info you need, search KB first.
- Anything useful you see, dump there `a_very_descriptive_file_name.md`.
- Jot down obstacles and how you solved them.
- Note key design decisions
- Keep a running list of key issues you repeatedly encounter and how you solved them.
- When asked to commit, you should review the full context since the last commit, consider
  a. What issues or obstacles did we run into? Should we expand the knowledge base to cover it?
  b. What articles were very useful? Do we need to update these?
