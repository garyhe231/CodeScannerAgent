"""In-memory session store for scanned repos and conversation history."""
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class Session:
    repo_path: str
    files: List[Dict]         # {"path": ..., "content": ...}
    repo_context: str         # concatenated source text
    file_tree: str            # newline-separated paths
    summary: Optional[str] = None
    history: List[Dict] = field(default_factory=list)  # conversation turns


# Single shared session (one repo at a time)
_current: Optional[Session] = None


def set_session(session: Session) -> None:
    global _current
    _current = session


def get_session() -> Optional[Session]:
    return _current


def clear_session() -> None:
    global _current
    _current = None


def append_turn(user_msg: str, assistant_msg: str) -> None:
    if _current is None:
        return
    _current.history.append({"role": "user", "content": user_msg})
    _current.history.append({"role": "assistant", "content": assistant_msg})
