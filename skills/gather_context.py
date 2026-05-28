"""Gather repo file context relevant to an issue."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

DEFAULT_MAX_FILES = 12
DEFAULT_MAX_BYTES_PER_FILE = 8_000
DEFAULT_MAX_TOTAL_BYTES = 60_000

CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".rb", ".php", ".cs", ".cpp", ".c", ".h", ".hpp", ".kt",
    ".swift", ".md", ".yml", ".yaml", ".toml", ".json",
}

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__",
    "dist", "build", ".next", ".cache", "target", ".idea", ".vscode",
}


def _iter_repo_files(repo_root: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in CODE_EXTS:
                yield p


def _tokenize(text: str) -> set[str]:
    return {
        t.lower()
        for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text or "")
    }


def _score(path: Path, repo_root: Path, keywords: set[str]) -> int:
    rel = str(path.relative_to(repo_root)).lower()
    score = 0
    for kw in keywords:
        if kw in rel:
            score += 5
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return score
    text_low = text.lower()
    for kw in keywords:
        # cheap occurrence count, capped
        c = text_low.count(kw)
        if c:
            score += min(c, 10)
    return score


def gather_context(
    issue_text: str,
    repo_root: str = ".",
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes_per_file: int = DEFAULT_MAX_BYTES_PER_FILE,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    explicit_paths: Optional[list[str]] = None,
) -> str:
    """Scan repo, rank files by keyword overlap with issue_text, return concat string."""
    root = Path(repo_root).resolve()
    if not root.exists():
        raise FileNotFoundError(f"repo_root not found: {root}")

    keywords = _tokenize(issue_text)
    # noise stopwords
    stop = {"the", "and", "for", "with", "this", "that", "from", "should", "would"}
    keywords -= stop

    explicit_paths = explicit_paths or []
    explicit_set: list[Path] = []
    for p in explicit_paths:
        cand = (root / p).resolve()
        if cand.exists() and cand.is_file():
            explicit_set.append(cand)

    scored: list[tuple[int, Path]] = []
    for p in _iter_repo_files(root):
        s = _score(p, root, keywords)
        if s > 0:
            scored.append((s, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked: list[Path] = list(dict.fromkeys(explicit_set + [p for _, p in scored]))
    picked = picked[:max_files]

    parts: list[str] = []
    total = 0
    for p in picked:
        try:
            data = p.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            logger.warning("read failed %s: %s", p, e)
            continue
        snippet = data[:max_bytes_per_file]
        rel = p.relative_to(root).as_posix()
        chunk = f"\n=== FILE: {rel} ===\n{snippet}\n"
        if total + len(chunk) > max_total_bytes:
            break
        parts.append(chunk)
        total += len(chunk)

    if not parts:
        return "(no relevant files found)"
    return "".join(parts)
