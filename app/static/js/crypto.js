'use strict';

// End-to-end encryption. Each room has a random 256-bit key that only lives in
// the invite link after the '#', and browsers never send that part to the
// server. Messages are sealed with AES-GCM before they leave the browser, so
// the server only ever relays scrambled text.
const CipherCrypto = (() => {
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  const KEY_RE = /^[A-Za-z0-9_-]{43}$/;

  function toB64u(bytes) {
    let bin = '';
    bytes.forEach(b => { bin += String.fromCharCode(b); });
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function fromB64u(str) {
    const b64 = str.replace(/-/g, '+').replace(/_/g, '/');
    const bin = atob(b64 + '==='.slice((b64.length + 3) % 4));
    return Uint8Array.from(bin, c => c.charCodeAt(0));
  }

  function available() {
    return Boolean(window.isSecureContext && window.crypto && crypto.subtle);
  }

  function newKey() {
    return toB64u(crypto.getRandomValues(new Uint8Array(32)));
  }

  async function hashWithKey(label, keyStr) {
    const data = new Uint8Array([...enc.encode(label), ...fromB64u(keyStr)]);
    return new Uint8Array(await crypto.subtle.digest('SHA-256', data));
  }

  // A one-way hash the server keeps to check invite links. It can't be turned back into the key.
  async function keyCheck(keyStr) {
    return toB64u(await hashWithKey('cipher/v1/key-check:', keyStr));
  }

  // Everyone holding the same key sees the same code, e.g. "3F2A 91BC 0D7E"
  async function safetyCode(keyStr) {
    const hex = Array.from((await hashWithKey('cipher/v1/safety:', keyStr)).slice(0, 6),
                           b => b.toString(16).padStart(2, '0').toUpperCase()).join('');
    return hex.match(/.{4}/g).join(' ');
  }

  function importKey(keyStr) {
    return crypto.subtle.importKey('raw', fromB64u(keyStr), 'AES-GCM', false, ['encrypt', 'decrypt']);
  }

  // Tying each message to its room stops the server replaying it into another room
  function sealParams(iv, room) {
    return { name: 'AES-GCM', iv, additionalData: enc.encode('cipher/v1/room:' + room) };
  }

  async function encrypt(key, room, body) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const sealed = new Uint8Array(await crypto.subtle.encrypt(
      sealParams(iv, room), key, enc.encode(JSON.stringify(body))));
    const out = new Uint8Array(iv.length + sealed.length);
    out.set(iv);
    out.set(sealed, iv.length);
    return toB64u(out);
  }

  async function decrypt(key, room, str) {
    const buf = fromB64u(str);
    const plain = await crypto.subtle.decrypt(sealParams(buf.slice(0, 12), room), key, buf.slice(12));
    return JSON.parse(dec.decode(plain));
  }

  // Display names are sealed with the room key too, so the server never reads them
  const NAME_AAD = enc.encode('cipher/v1/name');

  async function sealName(key, name) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const sealed = new Uint8Array(await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv, additionalData: NAME_AAD }, key, enc.encode(name)));
    const out = new Uint8Array(iv.length + sealed.length);
    out.set(iv);
    out.set(sealed, iv.length);
    return toB64u(out);
  }

  async function openName(key, str) {
    const buf = fromB64u(str);
    const plain = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: buf.slice(0, 12), additionalData: NAME_AAD }, key, buf.slice(12));
    return dec.decode(plain);
  }

  // Same name (any capitalisation) -> same tag, so the server can refuse a
  // duplicate name without learning it. Keyed by the room key, so it can't be guessed.
  async function nameTag(keyStr, name) {
    const tagKey = await crypto.subtle.importKey(
      'raw', await hashWithKey('cipher/v1/name-tag-key:', keyStr),
      { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    const sig = await crypto.subtle.sign('HMAC', tagKey, enc.encode(name.toLowerCase()));
    return toB64u(new Uint8Array(sig));
  }

  // Same rules the server used to check: 2–30 letters, numbers, spaces, hyphens, apostrophes
  const NAME_RE = /^[\p{L}\p{N}\p{M}_ '\-]+$/u;
  function nameError(name) {
    if (!name) return 'Enter a name to continue.';
    if (name.length < 2 || name.length > 30) return 'Name must be between 2 and 30 characters.';
    if (!NAME_RE.test(name)) return 'Letters, numbers, spaces, hyphens, and apostrophes only.';
    return null;
  }

  // Pulls the code and key out of a pasted invite link (…/cipher/r/CODE#KEY)
  function parseInvite(text) {
    const m = /\/r\/([A-Za-z0-9]{8})[^#\s]*#([A-Za-z0-9_-]{43})/.exec(text);
    return m ? { code: m[1].toUpperCase(), key: m[2] } : null;
  }

  return {
    KEY_RE, available, newKey, keyCheck, safetyCode, importKey, encrypt, decrypt,
    sealName, openName, nameTag, nameError, parseInvite,
  };
})();
