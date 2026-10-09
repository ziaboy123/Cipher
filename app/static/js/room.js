'use strict';

// Name and code come from data attributes (inline scripts are blocked by the CSP)
const shellEl    = document.getElementById('room-shell');
const MY_NAME    = shellEl.dataset.name;
const ROOM_CODE  = shellEl.dataset.code;

// The room key arrives after the '#' of the invite link, which never reaches the
// server. Keep it in this tab only (so a refresh still works) and take it out of
// the address bar.
const KEY_STORE = 'cipher:' + ROOM_CODE;
function loadKey() {
  const fromHash = location.hash.slice(1);
  let key = CipherCrypto.KEY_RE.test(fromHash) ? fromHash : null;
  try {
    if (key) sessionStorage.setItem(KEY_STORE, key);
    else key = sessionStorage.getItem(KEY_STORE);
  } catch { /* storage blocked: the key just won't survive a refresh */ }
  if (location.hash) history.replaceState(null, '', location.pathname);
  return key;
}
function forgetKey() {
  try { sessionStorage.removeItem(KEY_STORE); } catch {}
}
const KEY_STR = loadKey();
const INVITE_LINK = `${location.origin}/cipher/r/${ROOM_CODE}#${KEY_STR}`;
let cryptoKey = null;

// iOS Safari keyboard fix — keyboard doesn't resize viewport, so we use
// visualViewport to keep the shell exactly as tall as the visible area.
if (window.visualViewport) {
  const shell = document.getElementById('room-shell');
  const onViewportResize = () => {
    shell.style.height = window.visualViewport.height + 'px';
  };
  window.visualViewport.addEventListener('resize', onViewportResize);
  window.visualViewport.addEventListener('scroll', onViewportResize);
}

const GROUP_TIMEOUT_MS = 90_000;

// ── DOM ───────────────────────────────────────────────────────────────────────
const messagesEl    = document.getElementById('messages');
const msgInput      = document.getElementById('msg-input');
const sendBtn       = document.getElementById('send-btn');
const liveDot       = document.getElementById('live-dot');
const memberCountEl = document.getElementById('member-count');
const membersBtn    = document.getElementById('members-btn');
const membersPopover= document.getElementById('members-popover');
const popoverList   = document.getElementById('popover-list');
const codeWrap      = document.getElementById('code-wrap');
const copyIcon      = document.getElementById('copy-icon');
const typingDots    = document.getElementById('typing-dots');
const typingText    = document.getElementById('typing-text');
const charCounter   = document.getElementById('char-counter');
const safetyCodeEl  = document.getElementById('safety-code');
const lockedTag     = document.getElementById('locked-tag');
const lockBtn       = document.getElementById('lock-btn');   // creator only
const burnBtn       = document.getElementById('burn-btn');   // creator only

// ── State ─────────────────────────────────────────────────────────────────────
let lastSender  = null;
let lastTs      = 0;
let lastGroupEl = null;
let isTyping    = false;
let typingTimer = null;
let copyTimeout = null;
const typingUsers = new Set();

// ── Formatting ────────────────────────────────────────────────────────────────
function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function nearBottom() {
  return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 120;
}

function scrollBottom(force = false) {
  if (force || nearBottom()) messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ── Rendering ─────────────────────────────────────────────────────────────────
function appendSystem(msg) {
  const wrap = document.createElement('div');
  wrap.className = 'msg-system';
  const t = document.createElement('span');
  t.className = 'msg-system-text';
  t.textContent = msg.text;          // textContent — XSS-safe
  wrap.appendChild(t);
  messagesEl.appendChild(wrap);
  // A system message always breaks the current sender group
  lastSender  = null;
  lastGroupEl = null;
  scrollBottom();
}

function appendMessage(msg) {
  if (msg.type === 'system') { appendSystem(msg); return; }

  const isOwn  = msg.name === MY_NAME;
  const msgTs  = new Date(msg.ts).getTime();
  const inGroup = msg.name === lastSender && (msgTs - lastTs) < GROUP_TIMEOUT_MS && lastGroupEl;

  if (!inGroup) {
    const group = document.createElement('div');
    group.className = 'msg-group' + (isOwn ? ' msg-group-own' : '');

    const header = document.createElement('div');
    header.className = 'msg-group-header';

    if (!isOwn) {
      const sender = document.createElement('span');
      sender.className = 'msg-sender';
      sender.textContent = msg.name;
      header.appendChild(sender);
    }

    const ts = document.createElement('span');
    ts.className = 'msg-ts';
    ts.textContent = fmtTime(msg.ts);
    header.appendChild(ts);

    group.appendChild(header);
    messagesEl.appendChild(group);
    lastGroupEl = group;
  }

  lastSender = msg.name;
  lastTs     = new Date(msg.ts).getTime();

  const row    = document.createElement('div');
  row.className = 'msg-row';
  const bubble = document.createElement('div');
  if (msg.content === null) {
    bubble.className = 'msg-bubble msg-bubble-unreadable';
    bubble.textContent = "Couldn't decrypt this message.";
  } else {
    bubble.className = 'msg-bubble';
    bubble.textContent = msg.content;  // textContent — XSS-safe
  }
  row.appendChild(bubble);
  lastGroupEl.appendChild(row);

  scrollBottom();
}

// ── Typing indicator ──────────────────────────────────────────────────────────
function syncTypingUI() {
  const names = Array.from(typingUsers);
  if (!names.length) {
    typingDots.classList.remove('visible');
    typingText.textContent = '';
    return;
  }
  typingDots.classList.add('visible');
  if      (names.length === 1) typingText.textContent = `${names[0]} is typing`;
  else if (names.length === 2) typingText.textContent = `${names[0]} and ${names[1]} are typing`;
  else                         typingText.textContent = 'Several people are typing';
}

// ── Members ───────────────────────────────────────────────────────────────────
function syncMembers(names) {
  memberCountEl.textContent = names.length;
  popoverList.innerHTML = '';
  names.forEach(n => {
    const el = document.createElement('div');
    el.className = 'popover-member';
    el.textContent = n;
    if (n === MY_NAME) {
      const tag = document.createElement('span');
      tag.className = 'you-tag';
      tag.textContent = '(you)';
      el.appendChild(tag);
    }
    popoverList.appendChild(el);
  });
}

membersBtn.addEventListener('click', e => {
  e.stopPropagation();
  membersPopover.hidden = !membersPopover.hidden;
});
document.addEventListener('click', () => { membersPopover.hidden = true; });
membersPopover.addEventListener('click', e => e.stopPropagation());

// ── Copy room code ────────────────────────────────────────────────────────────
const ICON_COPY = `<svg width="12" height="12" viewBox="0 0 16 16" fill="none"><rect x="5" y="5" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.4"/><path d="M3 11H2a1 1 0 01-1-1V2a1 1 0 011-1h8a1 1 0 011 1v1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>`;
const ICON_CHECK = `<svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M3 8l4 4 6-7" stroke="#3EE08A" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

codeWrap.addEventListener('click', () => {
  navigator.clipboard.writeText(INVITE_LINK).then(() => {
    copyIcon.innerHTML = ICON_CHECK;
    copyIcon.classList.add('copied');
    clearTimeout(copyTimeout);
    copyTimeout = setTimeout(() => {
      copyIcon.innerHTML = ICON_COPY;
      copyIcon.classList.remove('copied');
    }, 1500);
  });
});

// ── Room closed ───────────────────────────────────────────────────────────────
function showOverlay(title, sub, redirect = true) {
  shellEl.style.position = 'relative';
  const overlay = document.createElement('div');
  overlay.className = 'room-closed-overlay';
  const t = document.createElement('p');
  t.className = 'room-closed-text';
  t.textContent = title;
  const s = document.createElement('p');
  s.className = 'room-closed-sub';
  s.textContent = sub;
  const a = document.createElement('a');
  a.className = 'room-closed-link';
  a.href = '/cipher/';
  a.textContent = 'Return home';
  overlay.append(t, s, a);
  shellEl.appendChild(overlay);
  // replace(): the back button shouldn't lead back into a dead room
  if (redirect) setTimeout(() => { location.replace('/cipher/'); }, 4000);
}

function showRoomClosed(data) {
  forgetKey();
  if (socket) socket.disconnect();
  if (data && data.burned) showOverlay('CHANNEL BURNED.', 'The creator ended it. Nothing was kept.');
  else                     showOverlay('CHANNEL TERMINATED.', 'This room no longer exists.');
}

// ── Encryption ────────────────────────────────────────────────────────────────
// Decrypting is async, so everything that renders goes through one queue to
// keep messages in the order they arrived. Sends are queued the same way.
let renderQueue = Promise.resolve();
let sendQueue   = Promise.resolve();
function enqueue(fn) { renderQueue = renderQueue.then(fn).catch(() => {}); }

async function openMessage(msg) {
  try {
    const body = await CipherCrypto.decrypt(cryptoKey, ROOM_CODE, msg.content);
    if (typeof body.t !== 'string') throw new Error('bad message');
    // The sender's name is sealed inside the message, so the server can't pin it on someone else
    if (body.n !== msg.name) {
      appendSystem({ text: `Hid a message whose sender didn't match (${msg.name}).`, ts: msg.ts });
      return null;
    }
    return { ...msg, content: body.t };
  } catch {
    return { ...msg, content: null };
  }
}

// ── Socket ────────────────────────────────────────────────────────────────────
let socket = null;

function connect() {
  socket = io({ transports: ['websocket', 'polling'], path: '/cipher/socket.io' });

  socket.on('connect', () => {
    liveDot.className = 'live-dot';
  });

  socket.on('connect_error', () => {
    liveDot.className = 'live-dot reconnecting';
  });

  socket.on('disconnect', reason => {
    liveDot.className = 'live-dot disconnected';
    if (reason === 'io client disconnect') return;  // we left on purpose
    appendSystem({ text: 'Connection lost. Attempting to reconnect…', ts: new Date().toISOString() });
  });

  socket.on('reconnect', () => {
    liveDot.className = 'live-dot';
    appendSystem({ text: 'Reconnected.', ts: new Date().toISOString() });
  });

  socket.on('room_state', data => {
    syncMembers(data.members || []);
    syncLock(Boolean(data.locked));
    scrollBottom(true);
  });

  socket.on('new_message', msg => {
    enqueue(async () => {
      const opened = await openMessage(msg);
      if (opened) appendMessage(opened);
      typingUsers.delete(msg.name);
      syncTypingUI();
    });
  });

  socket.on('system_message', msg => enqueue(() => appendMessage(msg)));

  socket.on('member_update', data => syncMembers(data.members || []));

  socket.on('lock_state', data => syncLock(Boolean(data.locked)));

  socket.on('user_typing', data => {
    typingUsers.add(data.name);
    syncTypingUI();
  });

  socket.on('user_stop_typing', data => {
    typingUsers.delete(data.name);
    syncTypingUI();
  });

  socket.on('room_closed', showRoomClosed);

  socket.on('error', data => {
    appendSystem({ text: data.message, ts: new Date().toISOString() });
  });
}

async function start() {
  if (!KEY_STR) {
    showOverlay('KEY MISSING.', 'This channel is end-to-end encrypted. Open the full invite link to read it.', false);
    return;
  }
  if (!CipherCrypto.available()) {
    showOverlay('CAN’T DECRYPT.', 'This browser can’t decrypt messages here. Open Cipher over https.', false);
    return;
  }
  cryptoKey = await CipherCrypto.importKey(KEY_STR);
  CipherCrypto.safetyCode(KEY_STR).then(c => { safetyCodeEl.textContent = c; });
  appendSystem({ text: 'Messages are end-to-end encrypted. Only people with the invite link can read them.', ts: new Date().toISOString() });
  connect();
}

start();

// ── Lock + burn (creator only) ────────────────────────────────────────────────
function syncLock(locked) {
  lockedTag.hidden = !locked;
  if (lockBtn) {
    lockBtn.dataset.locked = locked ? '1' : '';
    lockBtn.textContent = locked ? 'Unlock room' : 'Lock room';
  }
}

if (lockBtn) {
  lockBtn.addEventListener('click', () => {
    if (socket) socket.emit('lock', { locked: !lockBtn.dataset.locked });
  });
}

if (burnBtn) {
  let disarmTimer = null;
  burnBtn.addEventListener('click', () => {
    if (burnBtn.dataset.armed) {
      if (socket) socket.emit('burn');
      return;
    }
    // Two clicks to burn, so it can't happen by accident
    burnBtn.dataset.armed = '1';
    burnBtn.textContent = 'Click again to burn';
    clearTimeout(disarmTimer);
    disarmTimer = setTimeout(() => {
      delete burnBtn.dataset.armed;
      burnBtn.textContent = 'Burn channel';
    }, 3000);
  });
}

// ── Panic: Esc twice wipes the screen and leaves ──────────────────────────────
let lastEsc = 0;
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  const now = Date.now();
  if (now - lastEsc < 600) {
    messagesEl.replaceChildren();
    forgetKey();
    if (socket) socket.disconnect();
    location.replace('/cipher/');
  }
  lastEsc = now;
});

// ── Send ──────────────────────────────────────────────────────────────────────
function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || text.length > 1000 || !socket || !cryptoKey) return;
  msgInput.value = '';
  msgInput.style.height = 'auto';
  charCounter.className = 'char-counter';
  if (isTyping) {
    isTyping = false;
    clearTimeout(typingTimer);
    socket.emit('stop_typing');
  }
  sendQueue = sendQueue.then(async () => {
    const content = await CipherCrypto.encrypt(cryptoKey, ROOM_CODE, { n: MY_NAME, t: text });
    socket.emit('send_message', { content });
  }).catch(() => {
    appendSystem({ text: "Couldn't encrypt that message, so it wasn't sent.", ts: new Date().toISOString() });
  });
}

sendBtn.addEventListener('click', sendMessage);
msgInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

// ── Input behaviour ───────────────────────────────────────────────────────────
msgInput.addEventListener('input', () => {
  // Auto-resize
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 160) + 'px';

  // Character counter
  const rem = 1000 - msgInput.value.length;
  if      (rem <= 0)   { charCounter.textContent = '0';   charCounter.className = 'char-counter limit'; }
  else if (rem <= 100) { charCounter.textContent = rem;   charCounter.className = 'char-counter warn';  }
  else                 {                                   charCounter.className = 'char-counter';       }

  // Typing events
  if (!socket) return;
  if (!isTyping) { isTyping = true; socket.emit('typing'); }
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => {
    isTyping = false;
    socket.emit('stop_typing');
  }, 1500);
});

window.addEventListener('beforeunload', () => {
  if (isTyping && socket) socket.emit('stop_typing');
});
