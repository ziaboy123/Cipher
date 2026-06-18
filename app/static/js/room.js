'use strict';

// MY_NAME and ROOM_CODE injected by room.html

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
  bubble.className = 'msg-bubble';
  bubble.textContent = msg.content;  // textContent — XSS-safe
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
  membersPopover.style.display = membersPopover.style.display === 'none' ? 'block' : 'none';
});
document.addEventListener('click', () => { membersPopover.style.display = 'none'; });
membersPopover.addEventListener('click', e => e.stopPropagation());

// ── Copy room code ────────────────────────────────────────────────────────────
const ICON_COPY = `<svg width="12" height="12" viewBox="0 0 16 16" fill="none"><rect x="5" y="5" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.4"/><path d="M3 11H2a1 1 0 01-1-1V2a1 1 0 011-1h8a1 1 0 011 1v1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>`;
const ICON_CHECK = `<svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M3 8l4 4 6-7" stroke="#3EE08A" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

codeWrap.addEventListener('click', () => {
  navigator.clipboard.writeText(ROOM_CODE).then(() => {
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
function showRoomClosed() {
  const shell = document.getElementById('room-shell');
  shell.style.position = 'relative';
  const overlay = document.createElement('div');
  overlay.className = 'room-closed-overlay';
  overlay.innerHTML =
    '<p class="room-closed-text">CHANNEL TERMINATED.</p>' +
    '<p class="room-closed-sub">This room no longer exists.</p>' +
    '<a class="room-closed-link" href="/cipher/">Return home</a>';
  shell.appendChild(overlay);
  setTimeout(() => { window.location.href = '/cipher/'; }, 4000);
}

// ── Socket ────────────────────────────────────────────────────────────────────
const socket = io({ transports: ['websocket', 'polling'], path: '/cipher/socket.io' });

socket.on('connect', () => {
  liveDot.className = 'live-dot';
});

socket.on('connect_error', () => {
  liveDot.className = 'live-dot reconnecting';
});

socket.on('disconnect', () => {
  liveDot.className = 'live-dot disconnected';
  appendSystem({ text: 'Connection lost. Attempting to reconnect…', ts: new Date().toISOString() });
});

socket.on('reconnect', () => {
  liveDot.className = 'live-dot';
  appendSystem({ text: 'Reconnected.', ts: new Date().toISOString() });
});

socket.on('room_state', data => {
  syncMembers(data.members || []);
  (data.history || []).forEach(appendMessage);
  scrollBottom(true);
});

socket.on('new_message', msg => {
  appendMessage(msg);
  typingUsers.delete(msg.name);
  syncTypingUI();
});

socket.on('system_message', msg => appendMessage(msg));

socket.on('member_update', data => syncMembers(data.members || []));

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

// ── Send ──────────────────────────────────────────────────────────────────────
function sendMessage() {
  const content = msgInput.value.trim();
  if (!content || content.length > 1000) return;
  socket.emit('send_message', { content });
  msgInput.value = '';
  msgInput.style.height = 'auto';
  charCounter.className = 'char-counter';
  if (isTyping) {
    isTyping = false;
    clearTimeout(typingTimer);
    socket.emit('stop_typing');
  }
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
  if (!isTyping) { isTyping = true; socket.emit('typing'); }
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => {
    isTyping = false;
    socket.emit('stop_typing');
  }, 1500);
});

window.addEventListener('beforeunload', () => {
  if (isTyping) socket.emit('stop_typing');
});
