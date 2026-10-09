'use strict';

const nameInput  = document.getElementById('name');
const joinMirror = document.getElementById('join-name-mirror');
const formJoin   = document.getElementById('form-join');
const formCreate = document.getElementById('form-create');
const codeInput  = document.getElementById('code');

// An invite link arrives here as /cipher/?code=CODE#KEY (the redirect keeps the #KEY).
// Hold the key in memory and take it out of the address bar.
const hashKey = location.hash.slice(1);
let inviteKey = CipherCrypto.KEY_RE.test(hashKey) ? hashKey : null;
if (location.hash) history.replaceState(null, '', location.pathname + location.search);

function showError(text) {
  clearError();
  const p = document.createElement('p');
  p.className = 'error-line';
  p.textContent = text;
  formJoin.parentElement.appendChild(p);
}

function clearError() {
  const e = document.querySelector('.error-line');
  if (e) e.remove();
}

// Submit with the key riding along after the '#': the server's redirect keeps
// it, but the browser never sends it to the server.
async function submitWithKey(form, key) {
  form.elements.key_check.value = await CipherCrypto.keyCheck(key);
  form.action = form.action.split('#')[0] + '#' + key;
  form.submit();
}

formCreate.addEventListener('submit', e => {
  e.preventDefault();
  if (!CipherCrypto.available()) return showError("This browser can't encrypt messages here. Open Cipher over https.");
  submitWithKey(formCreate, CipherCrypto.newKey());
});

formJoin.addEventListener('submit', e => {
  e.preventDefault();
  joinMirror.value = nameInput.value;
  if (!CipherCrypto.available()) return showError("This browser can't encrypt messages here. Open Cipher over https.");
  if (!inviteKey) return showError("Paste the full invite link. The room code on its own can't unlock the channel.");
  submitWithKey(formJoin, inviteKey);
});

// Clear error on any keystroke
nameInput.addEventListener('input', clearError);
codeInput.addEventListener('input', clearError);

// Accept a pasted invite link (split into code + key), otherwise force an uppercase code
codeInput.addEventListener('input', () => {
  const invite = CipherCrypto.parseInvite(codeInput.value);
  if (invite) {
    codeInput.value = invite.code;
    inviteKey = invite.key;
    return;
  }
  const pos = codeInput.selectionStart;
  codeInput.value = codeInput.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8);
  codeInput.setSelectionRange(pos, pos);
});
