"""Post a comment on a GitHub issue or PR (both are issues in the GH API)."""
from __future__ import annotations

import logging
import os
from typing import Optional

from github import Github, GithubException

logger = logging.getLogger(__name__)


class PostCommentError(RuntimeError):
    pass


def post_comment(
    repo_full_name: str,
    issue_number: int,
    body: str,
    token: Optional[str] = None,
) -> str:
    """Add a comment to issue or PR. Returns comment HTML URL."""
    tok = token or os.environ.get("GITHUB_TOKEN")
    if not tok:
        raise PostCommentError("missing GITHUB_TOKEN")
    if not body or not body.strip():
        raise ValueError("body required")

    gh = Github(tok)
    try:
        repo = gh.get_repo(repo_full_name)
        issue = repo.get_issue(number=int(issue_number))
        comment = issue.create_comment(body)
    except GithubException as e:
        raise PostCommentError(f"comment failed: {e}") from e

    return comment.html_url
