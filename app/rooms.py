import secrets
import string
from datetime import datetime, timezone

_CODE_CHARS = string.ascii_uppercase + string.digits
_CODE_LEN = 8

# { code: { created_at, key_check, locked, members: {sid: {"name", "tag", "sess"}},
#           claims: {sealed name: sess} } }
#
# Messages are never stored, not even encrypted: the server only relays them.
# key_check is a one-way hash of the room key (made in the browser), so the
# server can tell whether someone has the real invite link without ever
# learning the key that decrypts the messages.
#
# Display names are encrypted in the browser too. "name" is that sealed blob,
# which the server passes around without being able to read. "tag" is a keyed
# hash of the name's lookalike skeleton (lowercased, accents and lookalike
# letters folded), so the server can spot a duplicate or lookalike name in a
# room without learning what the name is. The browser makes the tag, so the
# server can't check it matches the name: each browser also flags lookalikes itself.
#
# Each socket is one entry, but "sess" (a random id made at join) ties a
# person's tabs together, so two tabs still count as one person.
#
# "claims" remembers which join each sealed name belongs to. Every join seals
# its name fresh (new random IV), so a byte-for-byte copy of someone's sealed
# name can only be a replay of one read off the member list.
_store: dict[str, dict] = {}

# Past this many claims in a room, the ones from people who've left get forgotten
_MAX_CLAIMS = 1000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_code() -> str:
    while True:
        code = "".join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LEN))
        if code not in _store:
            return code


def valid_code(code: str) -> bool:
    return len(code) == _CODE_LEN and all(c in _CODE_CHARS for c in code)


def create(key_check: str) -> str:
    code = _gen_code()
    _store[code] = {
        "created_at": _now(),
        "key_check": key_check,
        "locked": False,
        "members": {},
        "claims": {},
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


def join(code: str, sid: str, name: str, tag: str, sess: str) -> None:
    _store[code]["members"][sid] = {"name": name, "tag": tag, "sess": sess}


def leave(code: str, sid: str) -> str | None:
    member = _store[code]["members"].pop(sid, None)
    return member["name"] if member else None


def session_sids(code: str, sess: str) -> list[str]:
    # This person's open sockets, oldest first
    return [sid for sid, m in _store[code]["members"].items() if m["sess"] == sess]


def _people(code: str) -> dict[str, dict]:
    # One entry per person, however many tabs they have open, in the order
    # they joined (claims are made at /join). Browsers number lookalike names
    # in this order, so it mustn't shuffle when someone refreshes.
    people: dict[str, dict] = {}
    for m in _store[code]["members"].values():
        people.setdefault(m["sess"], m)
    joined = {sess: i for i, sess in enumerate(_store[code]["claims"].values())}
    return dict(sorted(people.items(), key=lambda p: joined.get(p[0], len(joined))))


def member_names(code: str) -> list[str]:
    # Sealed names; browsers decrypt and sort them
    return [m["name"] for m in _people(code).values()]


def member_count(code: str) -> int:
    return len(_people(code))


def name_taken(code: str, tag: str, except_sess: str | None = None) -> bool:
    return any(secrets.compare_digest(m["tag"], tag)
               for sess, m in _people(code).items() if sess != except_sess)


def claim_name(code: str, name: str, sess: str) -> bool:
    # Everyone in a room gets everyone's sealed names, so without this a
    # modified browser could join with a copy of Bob's and be exactly "Bob",
    # even grabbing it while the real Bob is mid-refresh. First join to use it keeps it.
    claims = _store[code]["claims"]
    owner = claims.get(name)
    if owner is not None:
        return owner == sess
    if len(claims) >= _MAX_CLAIMS:
        here = set(_people(code))
        for n, s in list(claims.items()):
            if s not in here:
                del claims[n]
    claims[name] = sess
    return True


def make_msg(name: str, content: str) -> dict:
    return {"type": "message", "name": name, "content": content, "ts": _now()}


def make_event(event: str, name: str | None = None) -> dict:
    # The browser turns these into text ("Alex joined."), since only it can read names
    msg = {"type": "system", "event": event, "ts": _now()}
    if name:
        msg["name"] = name
    return msg
