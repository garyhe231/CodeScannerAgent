"""Walks a local directory and collects file contents for analysis."""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import SCANNABLE_EXTENSIONS, SKIP_DIRS, MAX_FILE_SIZE

GITHUB_URL_RE = re.compile(
    r'^https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?(/.*)?$'
)


def is_github_url(source: str) -> bool:
    return bool(GITHUB_URL_RE.match(source.strip()))


def clone_github_repo(url: str) -> str:
    """
    Shallow-clone a GitHub repo into a temp directory.
    Returns the temp directory path (caller must delete it when done).
    Raises ValueError on failure.
    """
    # Strip trailing slashes / .git / sub-paths — we want the bare repo URL
    clean_url = url.strip().rstrip('/')
    if not clean_url.endswith('.git'):
        # Drop any sub-path (e.g. /tree/main/...) and append .git
        clean_url = re.sub(r'(github\.com/[^/]+/[^/]+).*', r'\1', clean_url)
        clean_url += '.git'

    tmp_dir = tempfile.mkdtemp(prefix='codescan_')
    try:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', '--single-branch', clean_url, tmp_dir],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ValueError(f"git clone failed: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ValueError("git clone timed out after 120 seconds.")
    except FileNotFoundError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ValueError("git is not installed or not on PATH.")

    return tmp_dir


def _should_include(path: Path) -> bool:
    suffix = path.suffix.lower()
    name = path.name.lower()
    # Handle files like Dockerfile, Makefile (no extension)
    if suffix == "" and name in {"dockerfile", "makefile", "procfile", "gemfile"}:
        return True
    return suffix in SCANNABLE_EXTENSIONS


def scan_repo(root: str) -> Tuple[List[Dict], List[str]]:
    """
    Walk `root` and return (files, skipped_dirs).

    files: list of {"path": relative_path, "content": str}
    skipped_dirs: list of directory names that were pruned
    """
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise ValueError(f"Path does not exist: {root}")
    if not root_path.is_dir():
        raise ValueError(f"Path is not a directory: {root}")

    files = []
    skipped = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune skip dirs in-place so os.walk won't descend into them
        pruned = []
        kept = []
        for d in dirnames:
            if d in SKIP_DIRS or d.startswith("."):
                pruned.append(d)
            else:
                kept.append(d)
        dirnames[:] = kept
        skipped.extend(pruned)

        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if not _should_include(fpath):
                continue
            try:
                size = fpath.stat().st_size
                if size > MAX_FILE_SIZE:
                    files.append({
                        "path": str(fpath.relative_to(root_path)),
                        "content": f"[File too large to display: {size:,} bytes]",
                    })
                    continue
                content = fpath.read_text(encoding="utf-8", errors="replace")
                files.append({
                    "path": str(fpath.relative_to(root_path)),
                    "content": content,
                })
            except Exception as e:
                files.append({
                    "path": str(fpath.relative_to(root_path)),
                    "content": f"[Could not read file: {e}]",
                })

    return files, list(set(skipped))


def build_context(files: List[Dict], max_chars: int) -> str:
    """Concatenate file contents into a single context string, trimmed to max_chars."""
    parts = []
    total = 0
    for f in files:
        header = f"\n\n=== FILE: {f['path']} ===\n"
        body = f["content"]
        chunk = header + body
        if total + len(chunk) > max_chars:
            remaining = max_chars - total - len(header)
            if remaining > 200:
                parts.append(header + body[:remaining] + "\n[...truncated]")
            break
        parts.append(chunk)
        total += len(chunk)
    return "".join(parts)


def file_tree(files: List[Dict]) -> str:
    """Return a simple tree listing of all scanned file paths."""
    return "\n".join(f["path"] for f in files)
