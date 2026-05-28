# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Workshop repo demonstrating two parallel approaches to "Claude-driven GitHub automation":

1. **Action-native path** — `solve-issue.yml` and `explain-pr.yml` invoke `anthropics/claude-code-action@v1.0.130` directly. Claude runs inside the action and uses the GitHub CLI (`gh`) for all repo / PR operations.
2. **SDK-orchestrated path** — `claude-fix.yml` runs a Python orchestrator (`.github/scripts/claude_automation.py`) that drives discrete skills in `skills/` and calls the Anthropic SDK explicitly.

Both paths coexist on purpose so the two styles can be compared.

## Triggers

| Workflow | Event | Match |
|---|---|---|
| `solve-issue.yml` | `issues.labeled` or `issue_comment` | label `claude-solve` *or* comment `/solve` from owner/member/collaborator |
| `claude-fix.yml` | `issue_comment` | comment body contains `@claude fix this` (case-insensitive); ignored on PR comments |
| `explain-pr.yml` | `pull_request` opened / synchronize / reopened | always |

`solve-issue.yml` uses a `concurrency` group keyed by issue number — new triggers cancel in-flight runs for the same issue.

## SDK path architecture (`skills/` + orchestrator)

`.github/scripts/claude_automation.py` runs skills in order:

1. `gather_context.gather_context` — keyword-ranks repo files against the issue text, caps total bytes
2. `create_branch.create_branch` — `git fetch` base, `checkout -B`, push `-u origin`
3. `develop.develop` — calls Anthropic `messages.create` with a strict JSON contract (`commit_message` + `changes[]` with `action: write|delete`), applies changes with a repo-root path-traversal guard, then commits and pushes
4. `create_pr.create_pr` — opens PR via PyGithub, applies labels, links the issue with a comment
5. `post_comment.post_comment` — status updates after each step; on exception, posts a failure comment with a tail of the traceback

Branch naming convention: `claude/issue-<num>-<slug>` (slug derived from issue title).

The model's reply is parsed defensively: code fences stripped, then JSON extracted by the outermost `{ … }` span. Any path in `changes[].path` is resolved and rejected if it escapes the repo root.

## Auth model (important)

Only credential available is `CLAUDE_CODE_OAUTH_TOKEN` (Claude Code subscription OAuth bearer). No `ANTHROPIC_API_KEY`.

Implication: direct Messages API calls via the Anthropic Python SDK do **not** work with this token. The token authenticates the Claude Code CLI / action, not the model catalog. Symptoms when misused: SDK returns `401 invalid x-api-key` (sent as wrong header) or `404 model not_found_error` (model not allowed for OAuth scope).

`skills/develop.py` therefore shells out to the `claude` CLI in `--print` (headless) mode, passing `CLAUDE_CODE_OAUTH_TOKEN` through the subprocess env. The workflow installs the CLI via `npm install -g @anthropic-ai/claude-code`. Model is selected by alias (`sonnet`/`opus`/`haiku`), not a versioned ID.

Workflows that use `anthropics/claude-code-action` (`solve-issue`, `explain-pr`) need `id-token: write` so the action can exchange the OAuth token via OIDC — keep that permission when editing those workflows.

## Common commands

Install deps locally:
```
pip install -r requirements.txt
```

Run the orchestrator locally (mirrors the workflow env):
```
GITHUB_TOKEN=...               \
ANTHROPIC_API_KEY=...          \
REPO=owner/name                \
ISSUE_NUMBER=123               \
ISSUE_TITLE="..."              \
ISSUE_BODY="..."               \
COMMENT_BODY="@claude fix this"\
BASE_BRANCH=main               \
python .github/scripts/claude_automation.py
```

There is no test suite, lint config, or build step in this repo. Do not invent one.

## Conventions for changes here

- Keep the two automation paths separate. Don't merge `claude-fix.yml` logic into `solve-issue.yml` or vice versa.
- Pin `anthropics/claude-code-action` to an exact version (current: `v1.0.130`). The git history shows deliberate work to pin and harden this; do not loosen to `@v1`.
- Skills are plain functions, no class hierarchies. Each skill raises its own `*Error` subclass of `RuntimeError`. Preserve that shape when adding new ones.
- Default branch is `main`. PRs target `${{ github.event.repository.default_branch }}` in workflows, not a hardcoded name.
