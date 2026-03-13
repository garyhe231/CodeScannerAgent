"""Walks a local directory and collects file contents for analysis."""
import os
from pathlib import Path
from typing import Dict, List, Tuple

from app.config import SCANNABLE_EXTENSIONS, SKIP_DIRS, MAX_FILE_SIZE


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
