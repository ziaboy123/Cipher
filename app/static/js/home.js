'use strict';

// Mirror the shared name field into the join form on submit
const nameInput = document.getElementById('name');
const joinMirror = document.getElementById('join-name-mirror');
const formJoin = document.getElementById('form-join');
const formCreate = document.getElementById('form-create');

formJoin.addEventListener('submit', () => {
  joinMirror.value = nameInput.value;
});

// Clear error on any keystroke
nameInput.addEventListener('input', clearError);
document.getElementById('code').addEventListener('input', clearError);
function clearError() {
  const e = document.querySelector('.error-line');
  if (e) e.remove();
}

// Force uppercase on code input
const codeInput = document.getElementById('code');
codeInput.addEventListener('input', () => {
  const pos = codeInput.selectionStart;
  codeInput.value = codeInput.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
  codeInput.setSelectionRange(pos, pos);
});
