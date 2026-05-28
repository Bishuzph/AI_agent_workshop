"""Create a git branch from a base branch and push to remote."""
from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class CreateBranchError(RuntimeError):
    pass


def _run(cmd: list[str], cwd: Optional[str] = None) -> str:
    logger.info("run: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise CreateBranchError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    return proc.stdout.strip()


def create_branch(
    branch_name: str,
    base_branch: str = "main",
    cwd: Optional[str] = None,
    push: bool = True,
    remote: str = "origin",
) -> str:
    """Create new branch from base_branch, optionally push to remote.

    Returns the created branch name.
    """
    if not branch_name or not branch_name.strip():
        raise ValueError("branch_name required")

    branch_name = branch_name.strip()
    base_branch = base_branch.strip()

    _run(["git", "fetch", remote, base_branch], cwd=cwd)
    _run(["git", "checkout", base_branch], cwd=cwd)
    _run(["git", "pull", remote, base_branch, "--ff-only"], cwd=cwd)
    _run(["git", "checkout", "-B", branch_name], cwd=cwd)

    if push:
        _run(["git", "push", "-u", remote, branch_name], cwd=cwd)

    return branch_name
