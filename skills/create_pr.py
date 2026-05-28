"""Create a GitHub PR via PyGithub, label it, comment on origin issue."""
from __future__ import annotations

import logging
import os
from typing import Optional, Sequence

from github import Github, GithubException

logger = logging.getLogger(__name__)


class CreatePRError(RuntimeError):
    pass


def create_pr(
    repo_full_name: str,
    branch: str,
    title: str,
    body: str,
    base_branch: str = "main",
    token: Optional[str] = None,
    labels: Optional[Sequence[str]] = None,
    issue_number: Optional[int] = None,
    draft: bool = False,
) -> str:
    """Open a PR, apply labels, comment on the linking issue. Returns PR URL."""
    tok = token or os.environ.get("GITHUB_TOKEN")
    if not tok:
        raise CreatePRError("missing GITHUB_TOKEN")
    if not repo_full_name or "/" not in repo_full_name:
        raise ValueError("repo_full_name must be 'owner/repo'")

    gh = Github(tok)
    try:
        repo = gh.get_repo(repo_full_name)
    except GithubException as e:
        raise CreatePRError(f"repo lookup failed: {e}") from e

    try:
        pr = repo.create_pull(
            title=title,
            body=body,
            head=branch,
            base=base_branch,
            draft=draft,
        )
    except GithubException as e:
        raise CreatePRError(f"PR create failed: {e}") from e

    if labels:
        try:
            pr.add_to_labels(*labels)
        except GithubException as e:
            logger.warning("label apply failed: %s", e)

    if issue_number:
        try:
            issue = repo.get_issue(number=issue_number)
            issue.create_comment(f"PR opened: {pr.html_url}")
        except GithubException as e:
            logger.warning("issue comment failed: %s", e)

    return pr.html_url
