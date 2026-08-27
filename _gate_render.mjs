// 렌더 게이트 — **실제로 그려지는지** 본다.
//
// ★구문 게이트(node --check)만으로는 부족하다. 문법이 맞아도
//   `shown is not defined` 같은 실행 오류가 나면 drawAll() 이 중간에 죽고,
//   그 뒤 initTrend() 가 아예 안 불려 추이가 통째로 비어 버린다.
//   브라우저는 이때 조용하다 — 실제로 그렇게 당했다.
//
// 사용: node _gate_render.mjs   (실패하면 exit 1)
import { chromium } from 'rebrowser-playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FILE = 'file:///' + path.join(HERE, 'public', 'index.html').replace(/\\/g, '/');

const b = await chromium.launch({ channel: 'msedge' });
const p = await (await b.newContext({ viewport: { width: 1400, height: 900 } })).newPage();
const errs = [];
p.on('pageerror', e => errs.push(String(e).slice(0, 200)));
p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)); });

await p.goto(FILE, { waitUntil: 'load', timeout: 60000 });
await p.waitForTimeout(2500);

const r = await p.evaluate(() => {
  const o = {};
  // 그리는 함수를 하나씩 불러 어디서 죽는지 본다
  for (const fn of ['drawVerdict', 'drawSections', 'refreshCoinSel', 'drawDist', 'drawCov']) {
    try { eval(fn)(); o[fn] = 'ok'; } catch (e) { o[fn] = 'ERR ' + String(e).slice(0, 120); }
  }
  o.cells = document.querySelectorAll('.cell').length;
  o.cellsWithValue = document.querySelectorAll('.cell .v').length;
  o.rankCards = document.querySelectorAll('.rankcard').length;
  o.venueOpts = (document.getElementById('trVenue') || {}).options?.length ?? 0;
  o.sizeOpts = (document.getElementById('trSize') || {}).options?.length ?? 0;
  o.slipPaths = document.querySelectorAll('#svgSlip path').length;
  o.trendNoneShown = !(document.getElementById('trendNone') || {}).hidden;
  try { o.TS = String(TS); } catch (e) { o.TS = 'undef'; }
  return o;
});
await b.close();

let bad = 0;
const need = (name, cond, got) => {
  if (!cond) { bad++; console.log(`   ★${name} — ${got}`); }
  else console.log(`   ${name} — ${got}`);
};

console.log('★렌더 게이트');
for (const fn of ['drawVerdict', 'drawSections', 'refreshCoinSel', 'drawDist', 'drawCov']) {
  need(fn.padEnd(15), r[fn] === 'ok', r[fn]);
}
need('표 셀'.padEnd(15), r.cells > 50, `${r.cells}개 (값 ${r.cellsWithValue})`);
need('요약 카드'.padEnd(15), r.rankCards > 0, `${r.rankCards}개`);
need('추이 드롭다운'.padEnd(15), r.venueOpts > 0 && r.sizeOpts > 0,
     `venue ${r.venueOpts} · size ${r.sizeOpts} · TS=${r.TS}`);
// 이력이 2시점 미만이면 추이가 비는 게 정상이다
need('추이 선'.padEnd(15), r.slipPaths > 0 || r.trendNoneShown,
     `slip ${r.slipPaths}` + (r.trendNoneShown ? ' (이력 부족 안내 표시)' : ''));
need('JS 오류'.padEnd(15), errs.length === 0, errs.length ? errs[0] : '없음');

console.log(bad ? `\n★렌더 게이트 실패 — 문제 ${bad}건` : '\n★렌더 게이트 통과');
process.exit(bad ? 1 : 0);
