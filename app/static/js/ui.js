'use strict';

const $ = id => document.getElementById(id);

// ── Message renderer ──────────────────────────────────────────────────────────

const messagesEl   = $('messages');
const typingEl     = $('typing-indicator');
const typingTextEl = $('typing-text');

let lastSenderId = null;
let lastGroupEl  = null;

function formatTime(isoString) {
  const d = new Date(isoString);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDateSep(isoString) {
  const d = new Date(isoString);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], { month: 'long', day: 'numeric' });
}

let lastDate = null;

function maybeInjectDateSep(isoString) {
  const dateStr = new Date(isoString).toDateString();
  if (dateStr === lastDate) return;
  lastDate = dateStr;

  const sep = document.createElement('div');
  sep.className = 'date-sep';
  sep.innerHTML = `<div class="date-sep-line"></div><span class="date-sep-text">${formatDateSep(isoString)}</span><div class="date-sep-line"></div>`;
  messagesEl.appendChild(sep);
  lastSenderId = null; // Force new group after separator
  lastGroupEl = null;
}

function appendMessage(msg) {
  if (msg.type === 'system') {
    appendStatus(msg.content);
    lastSenderId = null;
    lastGroupEl = null;
    return;
  }

  maybeInjectDateSep(msg.created_at);

  const isOwn = msg.sender_id === CURRENT_ID;
  const sameGroup = msg.sender_id === lastSenderId;

  if (!sameGroup || !lastGroupEl) {
    // Start a new message group
    const group = document.createElement('div');
    group.className = 'msg-group' + (isOwn ? ' msg-own' : '');

    if (!isOwn) {
      // Header row with avatar + name + time
      const header = document.createElement('div');
      header.className = 'msg-group-header';

      const avatarSlot = document.createElement('div');
      avatarSlot.className = 'avatar avatar-sm';
      avatarSlot.textContent = msg.sender_initials || '?';

      const sender = document.createElement('span');
      sender.className = 'msg-sender';
      sender.textContent = msg.sender_display_name || msg.sender_username || 'Unknown';

      const time = document.createElement('span');
      time.className = 'msg-time';
      time.textContent = formatTime(msg.created_at);

      header.appendChild(avatarSlot);
      header.appendChild(sender);
      header.appendChild(time);
      group.appendChild(header);
    }

    messagesEl.appendChild(group);
    lastGroupEl = group;
    lastSenderId = msg.sender_id;
  }

  // Append bubble to current group
  const row = document.createElement('div');
  row.className = 'msg-row' + (isOwn ? ' msg-own' : '');

  if (!isOwn) {
    // Spacer to align under avatar
    const slot = document.createElement('div');
    slot.className = 'msg-avatar-slot';
    row.appendChild(slot);
  }

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble' + (isOwn ? ' own' : '');
  bubble.dataset.msgId = msg.id;

  if (msg.is_deleted) {
    bubble.classList.add('msg-deleted');
    bubble.textContent = 'This message was deleted.';
  } else {
    bubble.textContent = msg.content; // textContent is XSS-safe
  }

  row.appendChild(bubble);
  lastGroupEl.appendChild(row);

  scrollToBottom();
}

function appendStatus(text) {
  const el = document.createElement('div');
  el.className = 'msg-status';
  el.textContent = text;
  messagesEl.appendChild(el);
  scrollToBottom();
}

function scrollToBottom(force = false) {
  const threshold = 120;
  const nearBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < threshold;
  if (force || nearBottom) {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
}

// Load history
if (typeof HISTORY !== 'undefined') {
  HISTORY.forEach(appendMessage);
  scrollToBottom(true);
}

// ── Typing indicator ──────────────────────────────────────────────────────────

const typingUsers = new Map(); // user_id → display_name

function updateTypingUI() {
  const names = Array.from(typingUsers.values());
  if (names.length === 0) {
    typingEl.style.display = 'none';
    return;
  }
  typingEl.style.display = 'flex';
  if (names.length === 1) typingTextEl.textContent = `${names[0]} is typing`;
  else if (names.length === 2) typingTextEl.textContent = `${names[0]} and ${names[1]} are typing`;
  else typingTextEl.textContent = 'Several people are typing';
}

// ── Input auto-resize ─────────────────────────────────────────────────────────

const inputEl = $('message-input');

if (inputEl) {
  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
  });
}

// Expose so socket.js can call them
window.CipherUI = { appendMessage, appendStatus, updateTypingUI, typingUsers, scrollToBottom };
