# Cipher

A privacy-first, temporary real-time messaging platform. End-to-end encrypted. No accounts. No history. No trace.

Rooms exist only while occupied — create one, share the invite link, talk, leave. When the last person goes, the room is gone. Messages are encrypted in your browser and never stored, so there is nothing to leak afterwards.

## Tech Stack

- **Flask** + **Flask-SocketIO** (eventlet)
- **Flask-Limiter** (rate limiting per IP)
- **In-memory room store** — pure Python, no database or Redis required
- **Custom CSS design system** — near-monochrome dark palette, JetBrains Mono, single green accent

## How It Works

- Create a room → your browser makes a random 256-bit key and you get an invite link: `…/cipher/r/CODE#KEY`
- Share the link. The part after `#` never leaves the browser, so the server never sees the key
- Messages are encrypted before they're sent and relayed in real time via WebSocket; the server keeps none of them
- When the last member disconnects (or the creator burns the channel), the room is destroyed

No user accounts. No persistent identities. No request logs, and nothing loaded from third parties.

## End-to-End Encryption

- **AES-256-GCM** via the browser's Web Crypto API, a fresh random IV per message
- **Key in the link fragment.** Browsers don't send `#…` to servers, and a redirect keeps it, so the key travels with the invite link and nowhere else. It's removed from the address bar and kept in that tab's `sessionStorage` only so a refresh works
- **The code alone isn't enough.** The server stores a one-way SHA-256 hash of the key and only lets in people whose browser presents the matching hash. It can check invite links but can't recover the key
- **Encrypted names.** Display names are sealed with the room key in the browser too. The server only ever handles scrambled labels, and the "joined"/"left" lines are written by each browser. A keyed hash of the name (HMAC, derived from the room key) lets the server refuse a duplicate name in a room without learning it
- **Sealed sender.** The sender's name is also encrypted inside each message, so the server can't relabel a message as someone else's, and each message is bound to its room so it can't be replayed elsewhere
- **Safety code.** Everyone with the same key sees the same short code in the members panel; compare it to be sure you share the same link
- **Nothing stored.** The server relays ciphertext and keeps no messages at all, so late joiners only see what's said after they arrive

What the server can still see: how many people are in a room and when they come and go (as anonymous labels), message sizes and timing, and when someone is typing. It never sees names or message text. As with any web app, the server also delivers the JavaScript that does the encrypting; the strict CSP and self-hosted assets keep that code to files served by Cipher itself.

## Quick Start

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/ziaboy123/Cipher.git
cd Cipher
python -m venv .venv
```

Activate it:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and set a secret key:

```bash
cp .env.example .env
```

```env
SECRET_KEY=change-me-to-a-long-random-string
```

Settings default to production (secure cookies, no debug). For local development over plain http, add `CIPHER_DEV=1` to `.env`. Never set it on a server.

### 4. Run

```bash
python run.py
```

Open [http://127.0.0.1:5000/cipher/](http://127.0.0.1:5000/cipher/). Set `PORT` to use another port.

## Project Structure

```
app/
├── routes/
│   ├── home.py        # GET / — landing page, POST /create, POST /join
│   └── room.py        # GET /r/<code> — room view
├── sockets/
│   └── events.py      # connect, disconnect, send_message, typing, lock, burn
├── static/
│   ├── css/
│   │   ├── tokens.css           # Design tokens (colours, fonts, spacing)
│   │   ├── base.css             # Global resets, dot-grid background, animations
│   │   └── components/
│   │       ├── home.css         # Landing page styles
│   │       └── room.css         # Room shell, messages, input bar
│   │   ├── fonts.css            # Self-hosted Inter + JetBrains Mono
│   ├── fonts/                   # Variable woff2 files (SIL OFL 1.1)
│   └── js/
│       ├── crypto.js            # End-to-end encryption (Web Crypto, AES-GCM)
│       ├── home.js              # Landing page forms: makes the room key, reads invite links
│       ├── room.js              # Socket client, message rendering, typing indicator
│       └── vendor/              # Socket.IO client 4.7.5
├── templates/
│   ├── base.html      # HTML shell
│   ├── home.html      # CIPHER wordmark, create/join forms
│   └── room.html      # Room header, message list, input
├── rooms.py           # In-memory room store (sealed names + key hash; no messages)
├── csrf.py            # Lightweight CSRF without Flask-WTF
├── config.py          # Flask config (secret key, session cookie settings)
├── extensions.py      # SocketIO + Limiter instances
└── __init__.py        # App factory
run.py                 # Entrypoint — eventlet.monkey_patch() + socketio.run()
```

## Security

- **CSRF** — custom token validation using `secrets.compare_digest` on all form submissions
- **Rate limiting** — 5 room creates per hour, 20 joins per minute per visitor IP (read from Cloudflare's `CF-Connecting-IP` behind the tunnel)
- **Flood control** — at most 10 messages per 10 seconds per connection; Socket.IO packets capped at 16 KB
- **XSS** — all message content rendered via `textContent`, never `innerHTML`
- **Content Security Policy** — scripts, styles, fonts and the socket may only come from Cipher itself; no inline scripts or styles
- **Same-origin sockets** — Socket.IO rejects connections from other sites
- **Socket auth gate** — unauthenticated socket connections rejected on `connect`
- **Input validation** — names (2–30 chars, restricted pattern) are checked in the browser, since the server can't read them; the server only accepts well-formed ciphertext for names and messages (≤1000 characters before encryption)
- **Session security** — `HttpOnly`, `Secure`, `SameSite=Lax` cookie; the app refuses to start without a `SECRET_KEY`
- **No trace** — no access logs, no third-party fonts or CDNs, `no-referrer`, and pages are sent with `Cache-Control: no-store`

## Features

- End-to-end encrypted real-time messaging via WebSocket
- Invite link copy (code + key), or paste a link into the join box
- **Burn channel** (creator) — ends the room for everyone instantly, two clicks to confirm
- **Lock room** (creator) — no one new can join until it's unlocked
- **Panic key** — press Esc twice to wipe the screen, forget the key and leave
- Safety code to confirm everyone shares the same key
- Live typing indicators (cleared if someone's tab crashes)
- Member list with live presence count
- Message grouping — consecutive messages from the same sender are visually merged
- "CHANNEL TERMINATED." / "CHANNEL BURNED." overlays, then back home

## Future Ideas

- Configurable member cap per room
- Message self-destruct timers
- Unread count in browser tab title
- Room age counter in the header
