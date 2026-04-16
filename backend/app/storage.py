from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SessionPaths:
    session_id: str
    root: Path
    user_dir: Path
    rocky_dir: Path
    log_dir: Path
    log_file: Path


def data_root() -> Path:
    return Path(os.getenv("OMNIVOICE_CHAT_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))


def new_session() -> SessionPaths:
    sid = uuid.uuid4().hex
    return get_session_paths(sid)


def get_session_paths(session_id: str) -> SessionPaths:
    root = data_root() / "sessions" / session_id
    user_dir = root / "user"
    rocky_dir = root / "rocky"
    log_dir = data_root() / "logs"
    log_file = log_dir / f"{session_id}.jsonl"
    return SessionPaths(
        session_id=session_id,
        root=root,
        user_dir=user_dir,
        rocky_dir=rocky_dir,
        log_dir=log_dir,
        log_file=log_file,
    )


def ensure_session_dirs(sp: SessionPaths) -> None:
    sp.user_dir.mkdir(parents=True, exist_ok=True)
    sp.rocky_dir.mkdir(parents=True, exist_ok=True)
    sp.log_dir.mkdir(parents=True, exist_ok=True)


def append_log(sp: SessionPaths, event: dict) -> None:
    ensure_session_dirs(sp)
    payload = dict(event)
    payload.setdefault("ts", time.time())
    with sp.log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def delete_session_recordings(sp: SessionPaths) -> None:
    # Delete audio recordings, but keep the conversation log in `data/logs/`.
    if sp.root.exists():
        shutil.rmtree(sp.root, ignore_errors=True)

