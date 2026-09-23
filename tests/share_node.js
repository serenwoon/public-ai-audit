// 시험 도우미 — 브라우저 코드 public/share.js 를 node 에서 그대로 돌린다.
// stdin: {"op":"decode","hash":"#..."} 또는 {"op":"encode","text","situation","day"}  →  stdout: JSON
const Share = require('../public/share.js');

let buf = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (d) => { buf += d; });
process.stdin.on('end', async () => {
  const p = JSON.parse(buf);
  if (p.op === 'decode') {
    process.stdout.write(JSON.stringify(await Share.decodeFragment(p.hash)));
  } else {
    const fragment = await Share.encodeFragment({ text: p.text, situation: p.situation, day: p.day });
    process.stdout.write(JSON.stringify({ fragment }));
  }
});
