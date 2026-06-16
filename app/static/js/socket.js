'use strict';

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
const { appendMessage, appendStatus, updateTypingUI, typingUsers, scrollToBottom } = window.CipherUI;

const socket = io({ transports: ['websocket', 'polling'] });

// ── Connection lifecycle ──────────────────────────────────────────────────────

socket.on('connect', () => {
  socket.emit('join_conversation', { convo_id: CONVO_ID });
});

socket.on('disconnect', () => {
  appendStatus('Connection lost. Reconnecting…');
});

socket.on('reconnect', () => {
  socket.emit('join_conversation', { convo_id: CONVO_ID });
  appendStatus('Reconnected.');
});

// ── Incoming messages ─────────────────────────────────────────────────────────

socket.on('new_message', msg => {
  appendMessage(msg);
  // Clear typing state for sender
  typingUsers.delete(msg.sender_id);
  updateTypingUI();
});

// ── Typing indicators ─────────────────────────────────────────────────────────

socket.on('user_typing', data => {
  typingUsers.set(data.user_id, data.display_name);
  updateTypingUI();
});

socket.on('user_stop_typing', data => {
  typingUsers.delete(data.user_id);
  updateTypingUI();
});

// ── Presence ──────────────────────────────────────────────────────────────────

socket.on('presence', data => {
  if (typeof OTHER_ID !== 'undefined' && data.user_id === OTHER_ID) {
    const dot = document.getElementById('header-presence');
    const statusEl = document.getElementById('header-status');
    const isOnline = data.status === 'online';

    if (dot) {
      dot.classList.toggle('online', isOnline);
    }
    if (statusEl) {
      statusEl.textContent = isOnline ? 'Online' : 'Offline';
      statusEl.classList.toggle('online', isOnline);
    }
  }

  // Update sidebar dot
  const sidebarDot = document.getElementById(`dot-${data.user_id}`);
  if (sidebarDot) {
    sidebarDot.classList.toggle('online', data.status === 'online');
  }
});

// ── Sending messages ──────────────────────────────────────────────────────────

const inputEl  = document.getElementById('message-input');
const sendBtn  = document.getElementById('send-btn');

function sendMessage() {
  const content = inputEl.value.trim();
  if (!content || content.length > 2000) return;

  socket.emit('send_message', { convo_id: CONVO_ID, content });
  inputEl.value = '';
  inputEl.style.height = 'auto';

  // Stop typing
  if (isTyping) {
    isTyping = false;
    socket.emit('stop_typing', { convo_id: CONVO_ID });
  }
}

sendBtn?.addEventListener('click', sendMessage);

inputEl?.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ── Typing detection ──────────────────────────────────────────────────────────

let isTyping = false;
let typingTimer = null;
const TYPING_TIMEOUT = 1500;

inputEl?.addEventListener('input', () => {
  if (!isTyping) {
    isTyping = true;
    socket.emit('typing', { convo_id: CONVO_ID });
  }
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => {
    isTyping = false;
    socket.emit('stop_typing', { convo_id: CONVO_ID });
  }, TYPING_TIMEOUT);
});

// Stop typing when leaving the page
window.addEventListener('beforeunload', () => {
  if (isTyping) socket.emit('stop_typing', { convo_id: CONVO_ID });
  socket.emit('leave_conversation', { convo_id: CONVO_ID });
});
