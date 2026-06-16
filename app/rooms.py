import secrets
import string
from collections import deque
from datetime import datetime, timezone

_CODE_CHARS = string.ascii_uppercase + string.digits
_CODE_LEN = 8
_MSG_BUFFER = 50

# { code: { created_at, creator, members: {sid: name}, messages: deque } }
_store: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_code() -> str:
    while True:
        code = "".join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LEN))
        if code not in _store:
            return code


# ── Room lifecycle ────────────────────────────────────────────────────────────

def create(creator: str) -> str:
    code = _gen_code()
    _store[code] = {
        "created_at": _now(),
        "creator": creator,
        "members": {},
        "messages": deque(maxlen=_MSG_BUFFER),
    }
    return code


def exists(code: str) -> bool:
    return code in _store


def destroy(code: str) -> None:
    _store.pop(code, None)


# ── Members ───────────────────────────────────────────────────────────────────

def join(code: str, sid: str, name: str) -> None:
    _store[code]["members"][sid] = name


def leave(code: str, sid: str) -> str | None:
    """Remove member by SID. Returns their display name, or None."""
    return _store[code]["members"].pop(sid, None)


def member_names(code: str) -> list[str]:
    return sorted(_store[code]["members"].values())


def member_count(code: str) -> int:
    return len(_store[code]["members"])


def name_taken(code: str, name: str) -> bool:
    taken = {n.lower() for n in _store[code]["members"].values()}
    return name.lower() in taken


# ── Messages ──────────────────────────────────────────────────────────────────

def push(code: str, msg: dict) -> None:
    _store[code]["messages"].append(msg)


def history(code: str) -> list[dict]:
    return list(_store[code]["messages"])


def make_msg(name: str, content: str) -> dict:
    return {"type": "message", "name": name, "content": content, "ts": _now()}


def make_system(text: str) -> dict:
    return {"type": "system", "text": text, "ts": _now()}
