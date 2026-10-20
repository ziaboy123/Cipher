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

  // Names that look the same (any capitalisation, lookalike letters) -> same tag,
  // so the server can refuse a duplicate name without learning it. Keyed by the
  // room key, so it can't be guessed.
  async function nameTag(keyStr, name) {
    const tagKey = await crypto.subtle.importKey(
      'raw', await hashWithKey('cipher/v1/name-tag-key:', keyStr),
      { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    const sig = await crypto.subtle.sign('HMAC', tagKey, enc.encode(nameSkeleton(name)));
    return toB64u(new Uint8Array(sig));
  }

  // A lookalike name is the one way to pose as someone in here, and the server
  // can't read names to stop it. So names get tidied the same way before
  // sealing, before the tag, and when reading anyone else's: NFKC turns
  // fancy/fullwidth letters into plain ones, and invisible characters
  // (zero-width, bidi controls, joiners) are dropped.
  const INVISIBLE_RE = /[\p{Default_Ignorable_Code_Point}\p{Cf}\p{Cc}]/gu;
  function cleanName(name) {
    return name.normalize('NFKC').replace(INVISIBLE_RE, '')
      .replace(/\s+/gu, ' ').trim().normalize('NFKC');
  }

  // Alphabets a name can use. One per name, so nobody can slip a Cyrillic "о"
  // into "Bob". Latin can sit next to Chinese/Japanese/Korean, but only as
  // separate words ("Lily 李"), since a CJK sign inside a Latin word ("B〇b")
  // passes for a Latin letter.
  const SCRIPTS = ['Latin', 'Greek', 'Cyrillic', 'Armenian', 'Georgian', 'Hebrew', 'Arabic',
    'Devanagari', 'Bengali', 'Gurmukhi', 'Gujarati', 'Oriya', 'Tamil', 'Telugu', 'Kannada',
    'Malayalam', 'Sinhala', 'Thai', 'Lao', 'Myanmar', 'Khmer', 'Ethiopic',
    'Han', 'Hiragana', 'Katakana', 'Hangul', 'Bopomofo'].map(s => [s, new RegExp(`\\p{Script=${s}}`, 'u')]);
  const CJK = new Set(['Han', 'Hiragana', 'Katakana', 'Hangul', 'Bopomofo']);
  const SHARED_RE = /[\p{Script=Common}\p{Script=Inherited}]/u;  // spaces, 0-9, accents
  function scriptError(name) {
    const all = new Set();
    for (const word of name.split(' ')) {
      const used = new Set();
      for (const ch of word) {
        if (SHARED_RE.test(ch)) continue;
        const hit = SCRIPTS.find(([, re]) => re.test(ch));
        if (!hit) return "Letters from that alphabet can't be used in names here.";
        used.add(CJK.has(hit[0]) ? 'CJK' : hit[0]);
      }
      if (used.size > 1) return 'Use one alphabet per word, not a mix.';
      used.forEach(s => all.add(s));
    }
    if (all.size > 1 && !(all.size === 2 && all.has('Latin') && all.has('CJK'))) {
      return 'Use one alphabet for your name, not a mix.';
    }
    return null;
  }

  // 2–30 letters, numbers, spaces, hyphens, apostrophes. Accents have to sit
  // on a letter, and no more than three stacked up.
  const NAME_RE = /^[\p{L}\p{N}\p{M}_ '\-]+$/u;
  const STRAY_MARK_RE = /(^|[^\p{L}\p{M}])\p{M}|\p{M}{4}/u;
  function nameError(name) {
    if (!name) return 'Enter a name to continue.';
    // Only a name from a modified browser can trip this one
    if (name !== cleanName(name)) return 'That name has hidden characters in it.';
    if (name.length < 2 || name.length > 30) return 'Name must be between 2 and 30 characters.';
    if (!NAME_RE.test(name)) return 'Letters, numbers, spaces, hyphens, and apostrophes only.';
    if (STRAY_MARK_RE.test(name)) return 'Accent marks need a letter to sit on.';
    return scriptError(name);
  }

  // Roughly what a name looks like: lookalike letters from other alphabets
  // become their Latin twins, accents and strokes go, and I/l/1, 0/o, rn/m and
  // vv/w count as the same. Two people with the same skeleton could be mistaken for each other.
  const LOOKALIKE = Object.fromEntries((
    'АA ВB ЕE ЅS ІI ЈJ КK МM НH ОO РP СC ТT ХX УY ҮY ԚQ ԜW ӀI ҺH Ьb ' +
    'аa еe оo рp сc уy хx ѕs іi јj һh ԁd ԛq ԝw ӏl үy ьb гr пn ' +
    'ΑA ΒB ΕE ΖZ ΗH ΙI ΚK ΜM ΝN ΟO ΡP ΤT ΥY ΧX αa οo ρp ιi κk νv υu χx ωw ϲc ϳj γy ' +
    'օo սu հh ոn ցg զq ՏS ՕO ԼL ՍU ' +
    'ǀl ıi ɑa ɡg ɪi ʟl ʙb ʜh ɴn ʀr ʏy ᴀa ᴄc ᴅd ᴇe ᴊj ᴋk ᴍm ᴏo ᴘp ᴛt ᴜu ᴠv ᴡw ᴢz ꜱs ' +
    "øo ØO łl ŁL đd ĐD ħh ĦH ŧt ŦT ƀb ʼ' ʹ' ˈ' ʻ' ʽ' ꞌ'"
  ).split(' ').map(pair => [...pair]));
  // Chinese/Japanese/Korean signs that pass for Latin letters, or for each
  // other (Katakana ロ and Chinese 口). Done before NFD, which would split
  // every Korean syllable into these same jamo.
  const CJK_LOOKALIKE = Object.fromEntries((
    '〇O ロO 口O 囗O ㅇO ᄋO ᆼO ㅁO ᄆO ㅣl ᅵl 丨l 〡l エI 工I ㄴL ᄂL ㅌE ᄐE ㄷC ᄃC 匚C ' +
    '凵U 丫Y 乂X 乙Z 一- ー- ㅡ- ᅳ- カ力 ニ二 ハ八 ヘへ タ夕 ト卜'
  ).split(' ').map(pair => [...pair]));
  function nameSkeleton(name) {
    return cleanName(name)
      .replace(/./gu, c => CJK_LOOKALIKE[c] || c)
      .normalize('NFD')
      .replace(/([\p{Script=Latin}\p{Script=Greek}\p{Script=Cyrillic}])\p{M}+/gu, '$1')
      .replace(/./gu, c => LOOKALIKE[c] || c)
      .toLowerCase()
      .replace(/[l1|]/g, 'i').replace(/0/g, 'o').replace(/rn/g, 'm').replace(/vv/g, 'w');
  }

  // Pulls the code and key out of a pasted invite link (…/cipher/r/CODE#KEY)
  function parseInvite(text) {
    const m = /\/r\/([A-Za-z0-9]{8})[^#\s]*#([A-Za-z0-9_-]{43})/.exec(text);
    return m ? { code: m[1].toUpperCase(), key: m[2] } : null;
  }

  return {
    KEY_RE, available, newKey, keyCheck, safetyCode, importKey, encrypt, decrypt,
    sealName, openName, nameTag, cleanName, nameError, nameSkeleton, parseInvite,
  };
})();
