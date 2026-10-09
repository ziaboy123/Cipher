# Cipher

A privacy-first, temporary real-time messaging platform. No accounts. No history. No trace.

Rooms exist only while occupied — create one, share the code, talk, leave. When the last person goes, the room and everything in it is gone.

## Tech Stack

- **Flask** + **Flask-SocketIO** (eventlet)
- **Flask-Limiter** (rate limiting per IP)
- **In-memory room store** — pure Python, no database or Redis required
- **Custom CSS design system** — near-monochrome dark palette, JetBrains Mono, single green accent

## How It Works

- Create a room → get an 8-character alphanumeric code (~2.8 trillion combinations)
- Share the code with whoever you want in the room
- Messages are broadcast in real time via WebSocket
- When the last member disconnects, the room and all its messages are permanently destroyed

No user accounts. No persistent identities. No request logs, and nothing loaded from third parties.

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
│   └── events.py      # connect, disconnect, send_message, typing
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
│       ├── home.js              # Landing page form behaviour
│       ├── room.js              # Socket client, message rendering, typing indicator
│       └── vendor/              # Socket.IO client 4.7.5
├── templates/
│   ├── base.html      # HTML shell
│   ├── home.html      # CIPHER wordmark, create/join forms
│   └── room.html      # Room header, message list, input
├── rooms.py           # In-memory room store (no persistence)
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
- **Input validation** — name (2–30 chars, restricted pattern) and message (≤1000 chars) validated server-side
- **Session security** — `HttpOnly`, `Secure`, `SameSite=Lax` cookie; the app refuses to start without a `SECRET_KEY`
- **No trace** — no access logs, no third-party fonts or CDNs, `no-referrer`, and pages are sent with `Cache-Control: no-store`

## Features

- Real-time messaging via WebSocket
- Live typing indicators — shows who is typing
- Member list with live presence count
- Message grouping — consecutive messages from the same sender are visually merged
- Room code copy to clipboard
- "CHANNEL TERMINATED." overlay when a room is destroyed
- Auto-redirect to home 4 seconds after room closure

## Future Ideas

- Optional room passwords
- Configurable member cap per room
- Message self-destruct timers
- Unread count in browser tab title
- Mobile-optimised layout
