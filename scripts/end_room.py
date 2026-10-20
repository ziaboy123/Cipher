"""End one open Cipher room by its code, without restarting Cipher.

Run it on the server, from the app folder:

    cd /var/www/cipher && .venv/bin/python scripts/end_room.py ABCD1234

Everyone in that room sees it close; every other room carries on.
It talks to the running app on 127.0.0.1 (PORT, default 5000) with a token
derived from SECRET_KEY in .env, so it only works on the server itself.
"""
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip())
        return 2
    code = sys.argv[1].strip().upper()

    env = {**dotenv_values(Path(__file__).resolve().parent.parent / ".env"), **os.environ}
    secret = env.get("SECRET_KEY")
    if not secret:
        print("SECRET_KEY isn't set (.env next to run.py).")
        return 1
    # Must match app/operator.py
    token = hmac.new(secret.encode(), b"cipher/v1/operator", hashlib.sha256).hexdigest()

    req = urllib.request.Request(
        f"http://127.0.0.1:{env.get('PORT', '5000')}/_operator/end-room",
        data=json.dumps({"code": code}).encode(),
        headers={"Content-Type": "application/json", "X-Operator-Token": token},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never via a proxy
    try:
        with opener.open(req, timeout=10) as res:
            print(f"Room {json.load(res)['code']} ended.")
            return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            print(json.loads(body).get("error", body))
        except ValueError:
            print(f"Refused ({e.code}). Is this running on the server, with the right .env?")
        return 1
    except urllib.error.URLError as e:
        print(f"Couldn't reach Cipher on 127.0.0.1: {e.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
