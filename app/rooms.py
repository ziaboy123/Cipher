import secrets
import string
from datetime import datetime, timezone

_CODE_CHARS = string.ascii_uppercase + string.digits
_CODE_LEN = 8

# { code: { created_at, creator, key_check, locked, members: {sid: name} } }
#
# Messages are never stored, not even encrypted: the server only relays them.
# key_check is a one-way hash of the room key (made in the browser), so the
# server can tell whether someone has the real invite link without ever
# learning the key that decrypts the messages.
_store: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_code() -> str:
    while True:
        code = "".join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LEN))
        if code not in _store:
            return code


def create(creator: str, key_check: str) -> str:
    code = _gen_code()
    _store[code] = {
        "created_at": _now(),
        "creator": creator,
        "key_check": key_check,
        "locked": False,
        "members": {},
    }
    return code


def exists(code: str) -> bool:
    return code in _store


def destroy(code: str) -> None:
    _store.pop(code, None)


def key_matches(code: str, key_check: str) -> bool:
    return secrets.compare_digest(_store[code]["key_check"], key_check)


def set_locked(code: str, locked: bool) -> None:
    _store[code]["locked"] = locked


def is_locked(code: str) -> bool:
    return _store[code]["locked"]


def join(code: str, sid: str, name: str) -> None:
    _store[code]["members"][sid] = name


def leave(code: str, sid: str) -> str | None:
    return _store[code]["members"].pop(sid, None)


def member_names(code: str) -> list[str]:
    return sorted(_store[code]["members"].values())


def member_count(code: str) -> int:
    return len(_store[code]["members"])


def name_taken(code: str, name: str) -> bool:
    taken = {n.lower() for n in _store[code]["members"].values()}
    return name.lower() in taken


def make_msg(name: str, content: str) -> dict:
    return {"type": "message", "name": name, "content": content, "ts": _now()}


def make_system(text: str) -> dict:
    return {"type": "system", "text": text, "ts": _now()}
