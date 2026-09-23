// 결과 링크 — 브라우저 쪽. 서버 spike/share_link.py 와 같은 형식을 쓴다.
//   #v=1&d=YYYY-MM-DD&a=<base64url(zlib(답변))>[&s=<base64url(zlib(상황))>]
// # 뒤는 서버로 가지 않는다. 브라우저와 node(시험) 양쪽에서 돈다 — CompressionStream·Blob·Response·atob 가 둘 다 있다.
(function (root) {
  'use strict';
  const MAX_TEXT = 8000; // 풀었을 때 이보다 길면 버린다 (감리 API 상한과 같다)

  function b64urlEncode(bytes) {
    let bin = '';
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function b64urlDecode(s) {
    if (!/^[A-Za-z0-9_-]+$/.test(s)) throw new Error('base64url 아님');
    s = s.replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) s += '=';
    const bin = atob(s);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  async function pipe(bytes, stream) {
    const piped = new Blob([bytes]).stream().pipeThrough(stream);
    return new Uint8Array(await new Response(piped).arrayBuffer());
  }

  async function pack(text) {
    return b64urlEncode(await pipe(new TextEncoder().encode(text), new CompressionStream('deflate')));
  }

  async function unpack(v) {
    const text = new TextDecoder('utf-8', { fatal: true }).decode(await pipe(b64urlDecode(v), new DecompressionStream('deflate')));
    if (text.length > MAX_TEXT) throw new Error('너무 긺');
    return text;
  }

  function supported() {
    return typeof CompressionStream !== 'undefined' && typeof DecompressionStream !== 'undefined';
  }

  async function encodeFragment({ text, situation, day }) {
    const p = new URLSearchParams();
    p.set('v', '1');
    if (day) p.set('d', day);
    p.set('a', await pack(text));
    if (situation) p.set('s', await pack(situation));
    return p.toString();
  }

  // 링크의 # 부분 → {text, situation, day}. 형식이 아니거나 풀 수 없으면 null (던지지 않는다)
  async function decodeFragment(hash) {
    try {
      const p = new URLSearchParams(String(hash || '').replace(/^#/, ''));
      if (p.get('v') !== '1' || !p.get('a')) return null;
      const text = await unpack(p.get('a'));
      const situation = p.get('s') ? await unpack(p.get('s')) : '';
      const d = p.get('d') || '';
      return { text, situation, day: /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : null };
    } catch (e) {
      return null;
    }
  }

  const api = { supported, encodeFragment, decodeFragment };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Share = api;
})(typeof window !== 'undefined' ? window : globalThis);
