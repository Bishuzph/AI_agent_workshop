"""Use Claude Code CLI to generate code changes from a description, apply, commit.

Why CLI and not the Anthropic SDK?
  The repo's only available credential is CLAUDE_CODE_OAUTH_TOKEN, which is
  the OAuth bearer issued for a Claude Code subscription. That token does
  not grant access to the Messages API model catalog (returns 404 on most
  model IDs). The Claude Code CLI is the supported consumer of that token,
  so we shell out to it in headless mode and parse a strict JSON contract
  from stdout.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MODEL = "sonnet"  # Claude Code CLI accepts aliases: sonnet, opus, haiku

SYSTEM_PROMPT = """You are a senior software engineer. You receive an issue description and \
relevant repository file context. You must propose precise code changes.

Respond ONLY with a single JSON object (no markdown, no prose) of this shape:
{
  "commit_message": "<conventional commit subject line, <=72 chars>",
  "changes": [
    {"path": "<repo-relative path>", "action": "write"|"delete", "content": "<full new file content if action=write, else empty>"}
  ]
}

Rules:
- For action=write: include FULL final file content, not a diff.
- Use forward-slash paths relative to repo root.
- Keep changes minimal and focused on the issue.
- Do not invent files unrelated to the task.
"""


class DevelopError(RuntimeError):
    pass


def _run(cmd: list[str], cwd: Optional[str] = None) -> str:
    proc = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise DevelopError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    return proc.stdout.strip()


def _extract_json(text: str) -> dict:
    text = text.strip()
    # strip code fences if present
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    # find first { ... last }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise DevelopError(f"no JSON object in model output: {text[:300]}")
    return json.loads(text[start : end + 1])


def _safe_path(repo_root: Path, rel: str) -> Path:
    p = (repo_root / rel).resolve()
    root = repo_root.resolve()
    if root not in p.parents and p != root:
        raise DevelopError(f"path escapes repo root: {rel}")
    return p


def develop(
    description: str,
    file_context: str,
    repo_root: str = ".",
    api_key: Optional[str] = None,
    auth_token: Optional[str] = None,
    model: str = MODEL,
    max_tokens: int = 8000,
    commit: bool = True,
    push: bool = True,
    remote: str = "origin",
    branch: Optional[str] = None,
) -> dict:
    """Generate changes via Claude, apply, optionally commit and push.

    Auth: requires CLAUDE_CODE_OAUTH_TOKEN env (or auth_token arg). The
    api_key parameter is accepted for backwards compatibility but ignored;
    Claude Code CLI handles auth itself via the OAuth token.

    Returns dict: {"commit_message", "changes", "committed": bool, "pushed": bool}
    """
    if not description.strip():
        raise ValueError("description required")

    oauth = auth_token or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or api_key
    if not oauth:
        raise DevelopError("missing CLAUDE_CODE_OAUTH_TOKEN")

    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise DevelopError(
            "claude CLI not found on PATH. Install with: "
            "npm install -g @anthropic-ai/claude-code"
        )

    root = Path(repo_root).resolve()

    user_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"# Task\n{description}\n\n"
        f"# Repository file context\n{file_context}\n"
    )

    cli_env = os.environ.copy()
    cli_env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth

    logger.info("invoking claude CLI model=%s", model)
    proc = subprocess.run(
        [
            claude_bin,
            "--print",
            "--model", model,
            "--permission-mode", "bypassPermissions",
            user_prompt,
        ],
        cwd=str(root),
        env=cli_env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise DevelopError(
            f"claude CLI failed ({proc.returncode}):\n"
            f"stdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}"
        )

    plan = _extract_json(proc.stdout)

    commit_message = plan.get("commit_message") or "chore: automated change"
    changes = plan.get("changes") or []
    if not isinstance(changes, list) or not changes:
        raise DevelopError("model returned no changes")

    applied: list[str] = []
    for ch in changes:
        action = ch.get("action")
        rel = ch.get("path")
        if not rel or action not in {"write", "delete"}:
            raise DevelopError(f"invalid change entry: {ch}")
        target = _safe_path(root, rel)
        if action == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(ch.get("content", ""), encoding="utf-8")
            applied.append(rel)
        elif action == "delete":
            if target.exists():
                target.unlink()
            applied.append(rel)

    committed = False
    pushed = False
    if commit and applied:
        _run(["git", "add", "--", *applied], cwd=str(root))
        status = _run(["git", "status", "--porcelain"], cwd=str(root))
        if status:
            _run(["git", "commit", "-m", commit_message], cwd=str(root))
            committed = True
            if push:
                args = ["git", "push"]
                if branch:
                    args += ["-u", remote, branch]
                _run(args, cwd=str(root))
                pushed = True

    return {
        "commit_message": commit_message,
        "changes": applied,
        "committed": committed,
        "pushed": pushed,
    }
