'use strict';

// Name and code come from data attributes (inline scripts are blocked by the CSP)
const shellEl    = document.getElementById('room-shell');
// Your display name arrives sealed with the room key; it's opened once the key loads
const MY_SEALED  = shellEl.dataset.name;
let   MY_NAME    = null;
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

  // A name two people share can't say who sent what, so then only trust what this tab sent
  const isOwn  = msg.mine || (msg.name === MY_SEALED && !msg.shared);
  const msgTs  = new Date(msg.ts).getTime();
  const groupKey = msg.shared ? null : (isOwn ? 'you' : msg.name);
  const inGroup = groupKey && groupKey === lastSender && (msgTs - lastTs) < GROUP_TIMEOUT_MS && lastGroupEl;

  if (!inGroup) {
    const group = document.createElement('div');
    group.className = 'msg-group' + (isOwn ? ' msg-group-own' : '');

    const header = document.createElement('div');
    header.className = 'msg-group-header';

    if (!isOwn) {
      const sender = document.createElement('span');
      sender.className = 'msg-sender' + (msg.lookalike ? ' lookalike' : '');
      sender.textContent = msg.sender;
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

  lastSender = groupKey;
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
let typingRender = 0;
async function syncTypingUI() {
  const render = ++typingRender;
  const names = await Promise.all(Array.from(typingUsers, async s => labelOf(s, await nameOf(s)).text));
  if (render !== typingRender) return;  // a newer update already drew
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
let membersRender = 0;
async function syncMembers(sealedNames) {
  const render = ++membersRender;
  memberCountEl.textContent = sealedNames.length;
  const members = await Promise.all(sealedNames.map(async s => ({ sealed: s, name: await nameOf(s) })));
  if (render !== membersRender) return;
  roster = new Map(members.map(m => [m.sealed, m.name]));
  // The server lists each person once, so the same sealed name twice is two people using it
  copiesOf = new Map();
  sealedNames.forEach(s => copiesOf.set(s, (copiesOf.get(s) || 0) + 1));
  members.forEach(m => { m.label = labelOf(m.sealed, m.name); });
  warnLookalikes();
  members.sort((a, b) => a.label.text.localeCompare(b.label.text));
  popoverList.innerHTML = '';
  let youShown = false;
  members.forEach(({ sealed, label }) => {
    const el = document.createElement('div');
    el.className = 'popover-member' + (label.lookalike ? ' lookalike' : '');
    el.textContent = label.text;
    if (label.lookalike) el.title = 'Someone else here has a name that looks like this one';
    if (sealed === MY_SEALED && !youShown) {
      youShown = true;
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
  else if (data && data.ended) showOverlay('CHANNEL CLOSED.', 'The site operator closed this room. Nothing was kept.');
  else                     showOverlay('CHANNEL TERMINATED.', 'This room no longer exists.');
}

// ── Encryption ────────────────────────────────────────────────────────────────
// Decrypting is async, so everything that renders goes through one queue to
// keep messages in the order they arrived. Sends are queued the same way.
let renderQueue = Promise.resolve();
let sendQueue   = Promise.resolve();
function enqueue(fn) { renderQueue = renderQueue.then(fn).catch(() => {}); }

// Sealed name -> readable name, opened once and remembered
const openedNames = new Map();
function nameOf(sealed) {
  if (!openedNames.has(sealed)) {
    openedNames.set(sealed, CipherCrypto.openName(cryptoKey, sealed)
      .then(n => (CipherCrypto.nameError(n) ? 'Unknown' : n))
      .catch(() => 'Unknown'));
  }
  return openedNames.get(sealed);
}

// ── Lookalike names ───────────────────────────────────────────────────────────
// The server can't read names, so it can't stop two people picking names that
// look the same (a modified browser can even send a name tag that doesn't match
// its name). So every browser checks for itself: names that look alike get a
// number and a warning colour.
let roster = new Map();      // sealed name -> opened name, for everyone here now
let copiesOf = new Map();    // sealed name -> how many people here are using it
const lookNo = new Map();    // sealed name -> its number among lookalikes
const nextNo = new Map();    // name skeleton -> last number handed out
const warned = new Set();
const sentByMe = new Set();  // this tab's messages, until the server echoes them back

// { text: 'Bob' } normally, { text: 'Bob #2', lookalike: true } when someone
// else here has a name that looks like it, and '(2 people)' on the end when
// two people are using the very same sealed name (a copy off the member list;
// the server refuses that, this is in case it ever doesn't)
function labelOf(sealed, name) {
  let text = name;
  const skel = CipherCrypto.nameSkeleton(name);
  const twins = [...roster].filter(([s, n]) => s !== sealed && CipherCrypto.nameSkeleton(n) === skel);
  if (twins.length) {
    // Numbered in the order the server lists people (who joined first), so
    // everyone in the room sees the same numbers and the earlier one is #1
    for (const [s, n] of [...roster, [sealed, name]]) {
      if (lookNo.has(s) || CipherCrypto.nameSkeleton(n) !== skel) continue;
      nextNo.set(skel, (nextNo.get(skel) || 0) + 1);
      lookNo.set(s, nextNo.get(skel));
    }
  }
  // Once a name has had a number it keeps it (and the warning) for the rest of
  // this tab, so an impostor can't wait for the real person to leave and then
  // carry on as plain "Bob"
  const numbered = lookNo.has(sealed);
  if (numbered) text = `${name} #${lookNo.get(sealed)}`;
  const copies = copiesOf.get(sealed) || 1;
  if (copies > 1) text += ` (${copies} people)`;
  return { text, lookalike: numbered || twins.length > 0 || copies > 1, shared: copies > 1 };
}

// Say so once per set of lookalikes, so nobody trusts a name by mistake
function warnLookalikes() {
  const say = (key, text) => {
    if (warned.has(key)) return;
    warned.add(key);
    enqueue(() => appendSystem({ text, ts: new Date().toISOString() }));
  };
  copiesOf.forEach((copies, sealed) => {
    if (copies < 2) return;
    say(`same ${sealed}`, `Heads up: ${copies} people here are using the exact same name, ${roster.get(sealed)}, so you can't tell their messages apart. A name can't prove who someone is.`);
  });
  const bySkel = new Map();
  roster.forEach((name, sealed) => {
    const skel = CipherCrypto.nameSkeleton(name);
    bySkel.set(skel, [...(bySkel.get(skel) || []), sealed]);
  });
  bySkel.forEach(group => {
    if (group.length < 2) return;
    const names = group.map(s => labelOf(s, roster.get(s)).text).sort();
    say(group.slice().sort().join(' '), `Heads up: ${names.slice(0, -1).join(', ')} and ${names.at(-1)} have names that look alike. A name can't prove who someone is.`);
  });
}

// The server only says what happened; the browser fills in who
async function describeEvent(msg) {
  switch (msg.event) {
    case 'joined':   return `${labelOf(msg.name, await nameOf(msg.name)).text} joined.`;
    case 'left':     return `${labelOf(msg.name, await nameOf(msg.name)).text} left.`;
    case 'locked':   return 'Channel locked. No one new can join.';
    case 'unlocked': return 'Channel unlocked.';
    default:         return msg.text || '';
  }
}

async function openMessage(msg) {
  try {
    const body = await CipherCrypto.decrypt(cryptoKey, ROOM_CODE, msg.content);
    if (typeof body.t !== 'string') throw new Error('bad message');
    const sender = await nameOf(msg.name);
    // The sender's name is sealed inside the message too, so the server can't pin it on someone else
    const label = labelOf(msg.name, sender);
    if (body.n !== sender) {
      appendSystem({ text: `Hid a message whose sender didn't match (${label.text}).`, ts: msg.ts });
      return null;
    }
    return { ...msg, sender: label.text, lookalike: label.lookalike, shared: label.shared, content: body.t };
  } catch {
    const label = labelOf(msg.name, await nameOf(msg.name));
    return { ...msg, sender: label.text, lookalike: label.lookalike, shared: label.shared, content: null };
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
    if (reason === 'io server disconnect') {
      // The server closed this one on purpose (e.g. too many tabs), so socket.io won't retry
      appendSystem({ text: 'Disconnected. Refresh the page to reconnect.', ts: new Date().toISOString() });
      return;
    }
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
      const mine = sentByMe.delete(msg.content);
      const opened = await openMessage(msg);
      if (opened) appendMessage({ ...opened, mine });
      typingUsers.delete(msg.name);
      syncTypingUI();
    });
  });

  socket.on('system_message', msg => enqueue(async () => {
    appendSystem({ text: await describeEvent(msg), ts: msg.ts });
  }));

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
  MY_NAME = await nameOf(MY_SEALED);
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
    try { sessionStorage.removeItem('cipher:name'); } catch {}
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
    sentByMe.add(content);
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
