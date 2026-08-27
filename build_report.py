# -*- coding: utf-8 -*-
"""Liquidity benchmark → single offline HTML (English).

사용자 요청 반영(2026-08-19):
 · 체결률 표시 제거 — ★단 못 채운 칸은 빗금 + `unfilled` 한 단어로 남긴다.
   숫자는 없애되 "이건 다 못 산다"는 사실까지 지우면 화면이 거짓말을 한다.
   상세(체결률·표본수)는 마우스를 올리면 title 로 나온다.
 · 거래소 열을 **성적순**(왼쪽이 좋음) — 지금 보는 사이즈 기준, 페어별 순위의 평균
 · 코인 행을 **시총순**(BTC·ETH…)
 · 거래소 종합 · 하이퍼리퀴드 두 판 설명 · 공통상장 토글 · 시장 탭 → 제거
 · 메이저와 주식을 **위아래로 쭉**
 · 전체 영어

★남기는 정직성 장치
 · fill < 95% → 빗금 + 붉은 테두리 + `unfilled` + 순위 제외
 · 미상장 → `n/a` (0 으로 세지 않는다)
 · 색은 **행(페어) 안에서의 순위** — 절대 bps 로 칠하면 BTC 는 전부 파랑, ADA 는 전부 빨강
 · 수수료 제외 · 측정 시간대(미국장 마감 전) 명시
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = pathlib.Path(__file__).resolve().parent
D = json.loads((ROOT / 'data' / 'agg_latest.json').read_text(encoding='utf-8'))
OUT = ROOT / 'public' / 'index.html'
OUT.parent.mkdir(parents=True, exist_ok=True)
M = D['meta']

# ★순위 이력 — 없으면 빈 배열. 첫 실행에는 추이가 없는 게 정상이다.
HIST_P = ROOT / 'data' / 'rank_history.json'
HIST = json.loads(HIST_P.read_text(encoding='utf-8')) if HIST_P.exists() else []

# ★행 순서 — 시총/거래량 대략순. 사람이 아는 순서로 둔다.
ORDER = {
    'MAJOR': ['BTC', 'ETH', 'XRP', 'BNB', 'SOL', 'DOGE', 'ADA', 'LINK', 'AVAX', 'SUI'],
    'RWA':   ['NVDA', 'AAPL', 'GOOGL', 'META', 'TSLA', 'PLTR', 'COIN', 'MSTR', 'HOOD', 'XAU'],
}
LABEL = {'MAJOR': 'Major crypto perps', 'RWA': 'Equity & gold perps (RWA)'}

# ★측정 간격은 **실제로 잰 값**을 쓴다. "5분마다"라고 적어 놓고 다르면 거짓말이 된다.
_iv = M.get('interval_sec')
_every = ('%d min' % round(_iv / 60)) if _iv and _iv >= 60 else          (('%d sec' % _iv) if _iv else 'irregular interval')
SITE = 'Osaka, Japan'          # 수집 서버 위치 — 지역에 따라 접근 가능한 거래소가 다르다

HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Perp Liquidity Benchmark — where does GRVT stand?</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0b1220;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;font-size:13px;
     padding:18px 20px 60px}
.wrap{max-width:1560px;margin:0 auto}
h1{font-size:21px;color:#f1f5f9;font-weight:700;letter-spacing:-.3px}
h2{font-size:16px;color:#f1f5f9;margin:30px 0 6px;font-weight:700}
h2 .sm{font-weight:400;font-size:11.5px;color:#64748b;margin-left:9px}
.sub{color:#64748b;font-size:11.5px;margin-top:5px;line-height:1.7}
.sub b{color:#94a3b8}

.verdict{background:#111c31;border:1px solid #1e293b;border-radius:10px;padding:15px 18px;margin:16px 0 6px}
.vhead{font-size:14.5px;color:#f1f5f9;font-weight:700;line-height:1.6}
.rankrow{display:flex;gap:8px;flex-wrap:wrap;margin-top:11px}
.rankcard{background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:9px 13px;min-width:150px}
.rankcard .sz{font-size:10.5px;color:#64748b}
.rankcard .rk{font-size:19px;font-weight:800;margin-top:2px}
.rankcard .of{font-size:11px;color:#64748b;font-weight:400}
.rankcard .mv{font-size:10.5px;color:#94a3b8;margin-top:3px}
.why{color:#94a3b8;font-size:11.5px;margin-top:10px;line-height:1.75}

.ctrl{display:flex;gap:14px;flex-wrap:wrap;align-items:center;background:#0f172a;
      border:1px solid #1e293b;border-radius:8px;padding:9px 13px;margin:10px 0}
.ctrl b{font-size:11px;color:#64748b;font-weight:700;margin-right:5px}
.seg{display:inline-flex;border:1px solid #24344d;border-radius:6px;overflow:hidden}
.seg button{background:#0b1220;color:#94a3b8;border:0;padding:5px 12px;font-size:11.5px;
            cursor:pointer;font-family:inherit}
.seg button.on{background:#1d4ed8;color:#fff;font-weight:700}
.badge{font-size:10.5px;color:#64748b}

.tw{overflow-x:auto;border-radius:8px;border:1px solid #1e293b;background:#0f172a}
table{border-collapse:separate;border-spacing:0;width:100%}
th{padding:7px 9px;text-align:center;font-size:11px;font-weight:700;color:#cbd5e1;
   border-bottom:2px solid #1e293b;white-space:nowrap;background:#0f172a;position:sticky;top:0;z-index:8}
th .r{display:block;font-weight:400;font-size:9px;color:#475569;margin-top:1px}
td{padding:0;text-align:center;border-bottom:1px solid #172033;white-space:nowrap}
.pn{text-align:left;font-weight:700;color:#f1f5f9;padding:9px 13px;position:sticky;left:0;
    background:#131f35;z-index:5;border-right:1px solid #24344d;min-width:92px;font-size:13px}
.cell{padding:9px 8px;min-width:96px;line-height:1.25}
.cell .v{font-size:14.5px;font-weight:700}
.cell .m{font-size:9px;color:#dbe4f0;opacity:.6;margin-top:2px}
.cell.excl{background-image:repeating-linear-gradient(45deg,#0000 0 5px,#00000055 5px 10px);
           outline:1px solid #f87171;outline-offset:-2px}
.cell.excl .v{color:#fecaca}
.xtag{display:block;font-size:9px;color:#fca5a5;font-weight:700;margin-top:1px;letter-spacing:.3px}
/* ★표본이 덜 모인 칸 — 못 채운 것이 아니다. 옅게만 표시한다. */
.cell.thin{opacity:.55}
.xtag.thin{color:#7dd3fc;font-weight:400}
.cell.na{color:#3f4a5f;font-size:11px;padding:13px 8px}
/* ★호출 자체가 막힌 칸 — '상장 없음'과 전혀 다르다. 눈에 띄게 둔다. */
.cell.blk{background:#2a1a1a;color:#fca5a5;font-size:10.5px;padding:11px 8px;
          outline:1px solid #7f1d1d;outline-offset:-2px;font-weight:700}
.rk{display:inline-block;min-width:14px;font-size:9.5px;color:#e2e8f0;font-weight:700;opacity:.55}
.grvtcol{border-left:2px solid #94a3b8;border-right:2px solid #94a3b8}

.legend{display:flex;gap:13px;flex-wrap:wrap;align-items:center;font-size:11px;color:#94a3b8;margin:7px 0 5px}
.sw{width:13px;height:13px;border-radius:3px;display:inline-block;vertical-align:-2px;margin-right:4px}

.dist{height:15px;background:#0b1220;border-radius:3px;position:relative}
.dist .whisk{position:absolute;height:2px;top:6.5px;background:#334155}
.dist .box{position:absolute;height:11px;top:2px;background:#1e40af;border-radius:2px;opacity:.8}
.dist .med{position:absolute;width:2px;height:15px;background:#93c5fd}

.note{color:#64748b;font-size:11.5px;line-height:1.85;background:#0f172a;border:1px solid #1e293b;
      border-radius:8px;padding:13px 16px;margin-top:12px}
.note b{color:#cbd5e1}
.warn{color:#fca5a5}
.cov .y{color:#34d399;font-weight:700}
.cov .n{color:#334155}
.cov td,.cov th{font-size:11px}
.foot{color:#475569;font-size:10.5px;margin-top:28px;text-align:center;line-height:1.8}

/* 순위 추이 */
.trendbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:12px 0 6px}
.trendbar .tlab{color:#64748b;font-size:11px}
.trendbar select{background:#111c31;color:#e2e8f0;border:1px solid #24344d;border-radius:6px;
 padding:5px 8px;font-size:12px;font-family:inherit}
.tbtn{background:#111c31;color:#94a3b8;border:1px solid #24344d;border-radius:6px;
 padding:5px 11px;font-size:11.5px;cursor:pointer;font-family:inherit}
.tbtn.on{background:#173049;color:#7dd3fc;border-color:#2a4a6b}
#trendWrap{display:flex;flex-direction:column;gap:10px;margin:6px 0 4px}
.tchart{background:#0d1526;border:1px solid #1e293b;border-radius:9px;padding:10px 12px 4px}
.tcap{font-size:11.5px;color:#94a3b8;margin-bottom:2px}
.tcap span{color:#64748b;font-size:10.5px}
.tchart svg{width:100%;height:auto;display:block}
.ttable{overflow-x:auto;margin:8px 0}
.ttable table{border-collapse:collapse;font-size:11.5px;width:100%}
.ttable th{background:#111c31;color:#94a3b8;padding:5px 9px;text-align:center;
 font-weight:600;white-space:nowrap;position:sticky;top:0}
.ttable td{padding:4px 9px;border-top:1px solid #1a2438;color:#cbd5e1;text-align:center;
 font-variant-numeric:tabular-nums;white-space:nowrap}
.ttable td:first-child,.ttable th:first-child{text-align:left;color:#94a3b8}
.ttable .me{color:#7dd3fc;font-weight:700;background:#0f1e30}
.ttable i{color:#64748b;font-style:normal;font-size:10px;margin-left:4px}
</style></head><body><div class="wrap">

<h1>Perp Liquidity Benchmark &mdash; where does GRVT stand?</h1>
<div class="sub">
<b>__NV__ venues</b> &times; __NC__ pairs &times; 5 order sizes &middot;
order-book snapshot every <b>__EVERY__</b>, averaged over the last <b>__WIN__ hours</b><br>
<b>__ROUNDS__ rounds</b> &middot; __ROWS__ observations &middot; __SPAN__ KST &middot;
measured from <b>__SITE__</b><br>
Each figure is the <b>median</b> across all rounds in the window &mdash;
slippage in <b>bps</b> against mid, <b>lower is better</b>.
A cell is dropped from the ranking if it has fewer than <b>__MINN__ readings</b>
or fails to fill more than <b>__MAXSHORT__%</b> of the time.</div>

<div id="verdict" class="verdict"></div>

<div class="ctrl" style="margin-top:12px">
  <b>COST</b>
  <div class="seg" id="segFee"></div>
  <span class="badge" id="feeNote"></span>
</div>
<div class="note" id="feeTable" style="margin-top:6px;display:none"></div>

<!-- ─────────── 순위 추이 ───────────
     ★차트를 둘로 나눈 이유
       순위는 **상대적**이다. 7등에서 3등이 되었다고 우리가 좋아졌다는 뜻은 아니다 —
       남이 나빠졌을 수도 있다. 그래서 순위(위)와 실제 슬리피지(아래)를 나란히 둔다.
       한 축에 두 측정치를 겹치면 둘 다 못 읽는다. -->
<h2>Rank over time<span class="sm">how the standing moved, and whether it was us or them</span></h2>
<div class="trendbar">
  <span class="tlab">Venue</span><select id="trVenue"></select>
  <span class="tlab">Segment</span><select id="trGroup"></select>
  <span class="tlab">Order size</span><select id="trSize"></select>
  <button id="trTable" class="tbtn">Table view</button>
</div>
<div id="trendWrap">
  <div class="tchart"><div class="tcap">Median slippage <span>(bps; lower is better)</span></div>
    <svg id="svgSlip" viewBox="0 0 900 220" preserveAspectRatio="xMidYMid meet"></svg></div>
</div>
<div id="trendTable" class="ttable" hidden></div>
<div id="trendNone" class="sub" hidden>Only one snapshot so far — the trend appears once
  the collector has run a few more times.</div>

<div class="ctrl">
  <span><b>ORDER SIZE</b><span class="seg" id="segZ"></span></span>
  <span class="badge">Columns sorted <b>best &rarr; worst</b> for the selected size &middot;
    rows by market cap &middot; cell colour = rank <b>within that pair</b></span>
</div>

<div class="legend">
  <span style="color:#64748b">Rank in row:</span>
  <span><span class="sw" style="background:#064e3b"></span>best</span>
  <span><span class="sw" style="background:#155e3c"></span></span>
  <span><span class="sw" style="background:#78350f"></span></span>
  <span><span class="sw" style="background:#7f1d1d"></span>worst</span>
  <span style="color:#334155">|</span>
  <span><span class="sw" style="background-image:repeating-linear-gradient(45deg,#0000 0 5px,#0006 5px 10px);border:1px solid #f87171"></span>
    hatched <b style="color:#fca5a5">unfilled</b> &mdash; the book could not fill that size &middot;
    faded <b style="color:#7dd3fc">n=…</b> &mdash; too few readings yet (a venue we only started reaching recently);
    both are left out of the ranking</span>
  <span style="color:#334155">|</span>
  <span style="border-left:3px solid #94a3b8;padding-left:6px">GRVT</span>
  <span style="color:#475569">hover a cell for detail</span>
</div>

<div id="sections"></div>

<h2>Dispersion <span class="sm">&mdash; bar = p10&ndash;p90, box = p25&ndash;p75, light line = median. Wider means <b>it depends on when you trade</b></span></h2>
<div class="ctrl">
  <span><b>MARKET</b><span class="seg" id="segDG"></span></span>
  <span><b>PAIR</b><select id="selCoin" style="background:#0b1220;color:#e2e8f0;border:1px solid #24344d;
    border-radius:6px;padding:5px 9px;font-size:11.5px;font-family:inherit"></select></span>
</div>
<div class="tw"><table id="tblDist"></table></div>

<h2>Listing coverage <span class="sm">&mdash; pairs a venue does not list are absent, not zero</span></h2>
<div class="tw"><table id="tblCov" class="cov"></table></div>

<h2>How far to trust these numbers</h2>
<div class="note">
<b>Method</b> &mdash; public order books were fetched and a market order of the given USD size was walked
against the book; the gap between average fill price and mid is reported in bps. Buy and sell were
measured separately and pooled.<br>
<b>Contract units</b> &mdash; OKX, KuCoin and MEXC quote size in <b>contracts</b>, so contract size was
applied. Without it they would look 100&times;, 1000&times; and 10000&times; deeper (after conversion, BTC
top-of-book lands at $117k&ndash;$4.75M across venues &mdash; the same order of magnitude).<br>
<b>Price band</b> &mdash; fills stop at &plusmn;10% from mid, which exchanges reject anyway. Without this
cap a deep book gets swept to the end and <b>slippage looks better than it is</b>.<br>
<b class="warn">Unfilled orders were never invented</b> &mdash; when the book ran out, slippage was left
empty and the cell is marked <b>unfilled</b>. Padding the remainder at the last price would make thin
books look liquid.<br>
<b class="warn">Not yet modelled</b> &mdash; tick/step rounding and minimum notional, quotes that vanish
before execution, DEX sequencer latency, USDT/USD depeg (Extended quotes in USD).<br>
<b class="warn">Timing</b> &mdash; captured 19:37&ndash;23:38 KST, i.e. <b>before the US cash session
opens</b>. RWA rankings must be re-measured during US market hours.<br>
<b>Fees excluded</b> &mdash; tiers and promotions differ by venue and would blur the ranking.
Add taker fees on top for real cost.
</div>

<div class="foot">
source __SRC__ &middot; aggregated by _agg_liquidity.py &middot; single offline file<br>
Ranking uses only cells that filled the full size (&ge; 95%) with n &ge; 100 observations.
</div>
</div>

<script>
const D = __DATA__, ORDER = __ORDER__, LABEL = __LABEL__, HIST = __HIST__;
const MINN = D.meta.min_n || 100;

/* ═══════════ 순위 추이 ═══════════
   색은 둘뿐이다 — 고른 거래소 하나(HL)와 나머지 맥락선(CTX).
   거래소 10곳에 색 10개를 쓰면 아무도 못 읽는다. 정체는 **선 끝 이름표**로 밝힌다.
   (다크 배경 #0b1220 기준 대비 HL 8.7:1 · CTX 3.9:1 — 둘 다 마크 기준 3:1 이상) */
const HL = '#38bdf8', CTX = '#64748b', GRID = '#1e293b', INK = '#94a3b8';
let TV = 'grvt', TG = 'MAJOR', TS = null, TTable = false;

function hStamps(){ const s = new Set(); HIST.forEach(h => s.add(h.at)); return [...s].sort(); }
function hRows(){ return HIST.filter(h => h.group === TG && h.size === TS); }
function hVenues(){ const s = new Set(); HIST.forEach(h => Object.keys(h.ranks).forEach(v => s.add(v)));
                    return [...s].sort(); }

function fmtAt(a){ return String(a).slice(5, 16).replace('T', ' '); }

/** 한 장 그린다. pick(row) 이 값을 꺼내고, 축은 값 범위에서 만든다. */
function drawTrend(svgId, pick, invert, unit){
  const svg = document.getElementById(svgId);
  const rows = hRows().sort((a, b) => a.at < b.at ? -1 : 1);
  svg.innerHTML = '';
  if (rows.length < 2) return;
  const W = 900, H = 260;
  const L = 44, R = 96, T = 14, B = 26;               // 오른쪽은 이름표 자리
  const xs = rows.map(r => r.at);
  const vens = hVenues();
  let lo = Infinity, hi = -Infinity;
  vens.forEach(v => rows.forEach(r => { const y = pick(r, v);
    if (y != null) { lo = Math.min(lo, y); hi = Math.max(hi, y); } }));
  if (!isFinite(lo)) return;
  if (lo === hi) { lo -= 1; hi += 1; }
  if (invert) {
    // ★순위 축은 정수만. 0등이나 11등은 존재하지 않는다.
    lo = 1; hi = Math.max(hi, 2);
  } else {
    const pad = (hi - lo) * 0.12; lo -= pad; hi += pad;
  }
  const X = i => L + (W - L - R) * (xs.length < 2 ? 0.5 : i / (xs.length - 1));
  const Y = v => { const t = (v - lo) / (hi - lo); return invert ? T + (H - T - B) * t
                                                                : H - B - (H - T - B) * t; };
  const ns = 'http://www.w3.org/2000/svg';
  const add = (tag, at, txt) => { const e = document.createElementNS(ns, tag);
    for (const k in at) e.setAttribute(k, at[k]); if (txt != null) e.textContent = txt;
    svg.appendChild(e); return e; };

  // 축 — 눈에 띄지 않게. 데이터가 주인공이다.
  let tickVals = [];
  if (invert) {
    // 순위는 정수 눈금만 찍는다. 많으면 건너뛴다.
    const stepR = Math.ceil((hi - lo + 1) / 6);
    for (let v = lo; v <= hi; v += stepR) tickVals.push(v);
    if (tickVals[tickVals.length - 1] !== hi) tickVals.push(hi);
  } else {
    for (let i = 0; i <= 4; i++) tickVals.push(lo + (hi - lo) * i / 4);
  }
  tickVals.forEach(function (v) {
    const y = Y(v);
    add('line', {x1: L, y1: y, x2: W - R, y2: y, stroke: GRID, 'stroke-width': 1});
    add('text', {x: L - 7, y: y + 3.5, fill: INK, 'font-size': 10, 'text-anchor': 'end'},
        invert ? String(Math.round(v)) : v.toFixed(1));
  });
  const step = Math.max(1, Math.ceil(xs.length / 6));
  xs.forEach((a, i) => { if (i % step && i !== xs.length - 1) return;
    add('text', {x: X(i), y: H - 8, fill: INK, 'font-size': 10, 'text-anchor': 'middle'}, fmtAt(a)); });

  // 맥락선 먼저 — 고른 것이 위에 오도록
  const draw = (v, on) => {
    let d = '', last = null;
    rows.forEach((r, i) => { const y = pick(r, v);
      if (y == null) { return; }
      d += (d ? 'L' : 'M') + X(i) + ' ' + Y(y); last = {i: i, y: y}; });
    if (!d) return null;
    add('path', {d: d, fill: 'none', stroke: on ? HL : CTX,
                 'stroke-width': on ? 2.5 : 1.2, 'stroke-opacity': on ? 1 : .55,
                 'stroke-linejoin': 'round', 'stroke-linecap': 'round'});
    if (on) rows.forEach((r, i) => { const y = pick(r, v);
      if (y != null) add('circle', {cx: X(i), cy: Y(y), r: 3.5, fill: HL,
                                    stroke: '#0b1220', 'stroke-width': 2}); });
    return last;
  };
  const ends = [];
  vens.forEach(v => { if (v !== TV){ const e = draw(v, false); if (e) ends.push({v: v, e: e}); } });
  const mine = draw(TV, true);

  /* ★선 끝 이름표 — 색만으로 정체를 알리지 않기 위해서다(맥락선은 대비가 낮다).
     겹치면 못 읽으므로 자리를 잡아 준다. 고른 거래소는 **두 줄**(이름+값)을 쓰므로
     그만큼 자리를 비워 둬야 한다. 안 그러면 아랫줄이 다음 이름표와 포개진다. */
  const LH = 11.5, MINE_H = 24;                 // 한 줄 높이 · 고른 것이 차지하는 높이
  const slots = ends.map(o => ({v: o.v, y: Y(o.e.y), h: LH}));
  if (mine) slots.push({v: TV, y: Y(mine.y), h: MINE_H, me: true});
  slots.sort((a, b) => a.y - b.y);
  let prev = -99;
  slots.forEach(s => { if (s.y - prev < LH) s.y = prev + LH; prev = s.y + (s.h - LH); });
  // 아래로 넘치면 전체를 위로 되민다
  const over = prev + LH - (H - 4);
  if (over > 0) slots.forEach(s => s.y -= over);
  slots.forEach(s => {
    if (s.me) {
      add('text', {x: W - R + 8, y: s.y + 3.5, fill: HL, 'font-size': 11.5,
                   'font-weight': 700}, s.v);
      add('text', {x: W - R + 8, y: s.y + 16, fill: HL, 'font-size': 10, 'opacity': .8},
          invert ? ('#' + Math.round(mine.y)) : (mine.y.toFixed(2) + unit));
    } else {
      add('text', {x: W - R + 8, y: s.y + 3.5, fill: INK, 'font-size': 10}, s.v);
    }
  });
}

function drawTrendTable(){
  const rows = hRows().sort((a, b) => a.at < b.at ? -1 : 1);
  const vens = hVenues();
  let h = '<table><tr><th>Time</th>' + vens.map(v =>
      '<th' + (v === TV ? ' class="me"' : '') + '>' + v + '</th>').join('') + '</tr>';
  rows.forEach(r => { h += '<tr><td>' + fmtAt(r.at) + '</td>' + vens.map(v => {
    const c = r.ranks[v] || {};
    return '<td' + (v === TV ? ' class="me"' : '') + '>' +
           (c.rank ? c.rank + (c.med != null ? '<i>' + val(c).toFixed(2) + '</i>' : '') : '—') +
           '</td>'; }).join('') + '</tr>'; });
  document.getElementById('trendTable').innerHTML = h + '</table>';
}

function drawTrends(){
  const stamps = hStamps();
  const few = stamps.length < 2;
  document.getElementById('trendNone').hidden = !few;
  document.getElementById('trendWrap').hidden = few;
  if (few) return;
  drawTrend('svgSlip', (r, v) => (r.ranks[v] || {}).med, false, ' bps');
  if (TTable) drawTrendTable();
}

function initTrend(){
  const stamps = hStamps();
  if (!HIST.length){ document.getElementById('trendNone').hidden = false;
                     document.getElementById('trendWrap').hidden = true; return; }
  const sizes = [...new Set(HIST.map(h => h.size))].sort((a, b) => a - b);
  TS = sizes.indexOf(100000) >= 0 ? 100000 : sizes[0];
  const fill = (id, items, cur, on) => { const s = document.getElementById(id);
    s.innerHTML = items.map(x => '<option value="' + x[0] + '"' +
      (String(x[0]) === String(cur) ? ' selected' : '') + '>' + x[1] + '</option>').join('');
    s.onchange = function(){ on(s.value); drawTrends(); }; };
  fill('trVenue', hVenues().map(v => [v, v]), TV, v => TV = v);
  fill('trGroup', [...new Set(HIST.map(h => h.group))].map(g => [g, LABEL[g] || g]), TG, g => TG = g);
  fill('trSize', sizes.map(s => [s, '$' + s.toLocaleString()]), TS, s => TS = +s);
  const b = document.getElementById('trTable');
  b.onclick = function(){ TTable = !TTable;
    document.getElementById('trendTable').hidden = !TTable;
    b.classList.toggle('on', TTable); if (TTable) drawTrendTable(); };
  drawTrends();
}
const M = D.meta, VEN = M.venues, SZ = M.sizes;
const VNAME = {grvt:'GRVT', hyperliquid:'Hyperliquid', binance:'Binance', bybit:'Bybit',
  okx:'OKX', mexc:'MEXC', kucoin:'KuCoin', aster:'Aster', lighter:'Lighter', extended:'Extended'};
const CEX = ['binance','bybit','okx','mexc','kucoin'];
const GROUPS = ['MAJOR','RWA'];
let ZI = 2, DG = 'MAJOR', COIN = '__ALL__';
/* ★수수료 포함 여부 — 기본은 **제외**다(사용자 결정).
   수수료는 등급·프로모션에 따라 달라서 비교의 기준으로 삼기 어렵다.
   다만 "슬리피지는 좋은데 수수료가 비싼 곳"이 가려지므로 켤 수 있게 둔다. */
let WITHFEE = false;
/* 값 하나를 꺼낼 때는 언제나 이 함수를 쓴다 — 표·순위·색이 따로 놀지 않게. */
function val(c){ if(!c || c.med==null) return null;
  return WITHFEE ? c.med + (c.fee||0) : c.med; }
/* 분포 막대처럼 med 가 아닌 값을 옮길 때 쓴다 */
function FEE(c){ return WITHFEE ? (c && c.fee || 0) : 0; }

const fmtUsd = s => s>=1e6 ? '$'+(s/1e6)+'M' : '$'+(s/1000)+'k';
const coinsOf = g => (ORDER[g]||[]).filter(c => D.by_coin[g] && D.by_coin[g][c]);

/* colour = rank inside the row. Absolute bps would paint BTC (0.01) all blue and
   ADA (16) all red, so you could not tell who is cheap for that pair. */
function rankColor(rank, total){
  if(!rank || !total) return '#131f35';
  const t = total<=1 ? 0 : (rank-1)/(total-1);
  const st = [[6,78,59],[21,94,60],[120,53,15],[127,29,29]];
  const x = t*(st.length-1), i = Math.min(st.length-2, Math.floor(x)), f = x-i;
  const c = st[i].map((a,k)=>Math.round(a+(st[i+1][k]-a)*f));
  return 'rgb('+c[0]+','+c[1]+','+c[2]+')';
}

function rankRow(t, s){
  /* ★순위도 val() 로 잰다. 수수료를 켜면 순위가 실제로 바뀌어야 한다 —
     숫자만 바뀌고 줄이 그대로면 화면이 거짓말을 한다. */
  const arr = VEN.filter(v=>t[v]&&t[v][s]&&t[v][s].rankable&&t[v][s].med!=null)
                 .map(v=>[v,val(t[v][s])]).sort((a,b)=>a[1]-b[1]);
  const m={}; arr.forEach(([v],i)=>m[v]=i+1);
  return [m, arr.length];
}

/* column order = mean normalised rank across that group's pairs, for the selected size.
   Best on the left. Venues that never rank (always unfilled) fall to the end. */
function venueOrder(g, s){
  const bc = D.by_coin[g], coins = coinsOf(g), acc = {};
  VEN.forEach(v=>acc[v]={sum:0,n:0});
  for(const c of coins){
    const r = rankRow(bc[c], s), rk = r[0], n = r[1];
    for(const v of VEN) if(rk[v]){ acc[v].sum += rk[v]/n; acc[v].n++; }
  }
  return VEN.slice().sort((a,b)=>{
    const A = acc[a].n ? acc[a].sum/acc[a].n : 9, B = acc[b].n ? acc[b].sum/acc[b].n : 9;
    return A-B || a.localeCompare(b);
  });
}

function pairTable(g){
  const s = String(SZ[ZI]), bc = D.by_coin[g], coins = coinsOf(g), cols = venueOrder(g, s);
  let h = '<thead><tr><th style="text-align:left;position:sticky;left:0;background:#0f172a">Pair</th>'
        + cols.map((v,i)=>'<th class="'+(v==='grvt'?'grvtcol':'')+'">'+(VNAME[v]||v)
            + '<span class="r">'+(CEX.includes(v)?'CEX':'DEX')+' &middot; #'+(i+1)+'</span></th>').join('')
        + '</tr></thead><tbody>';
  for(const coin of coins){
    const t = bc[coin], r = rankRow(t, s), rk = r[0], n = r[1];
    h += '<tr><td class="pn">'+coin+'</td>';
    for(const v of cols){
      const c = t[v] && t[v][s];
      const cls = v==='grvt' ? 'grvtcol' : '';
      // ★호출이 막힌 칸은 '상장 없음'과 구분해 보여 준다.
      //   섞으면 차단당한 거래소가 조용히 빠져 화면이 거짓말을 한다.
      if(c && c.blocked){ h += '<td class="'+cls+'"><div class="cell blk" '
        + 'title="this server could not reach the venue - not a missing listing">blocked</div></td>'; continue; }
      if(!c || c.med==null){ h += '<td class="'+cls+'"><div class="cell na">n/a</div></td>'; continue; }
      const ex = !c.rankable;
      const shown = val(c);
      /* ★제외 사유를 구분한다. 둘은 전혀 다른 이야기다.
           thin   — 아직 표본이 덜 모였다(기다리면 해결된다)
           unfilled — 그 규모를 실제로 못 채운다(유동성이 없다)
         섞어서 unfilled 로만 쓰면 "바이낸스가 BTC 10만불을 못 산다"는
         말이 되어 버린다. 실제로 그렇게 보였다. */
      const thin = ex && c.fill >= 0.95;
      /* ★detail lives in the tooltip, not on the face of the cell */
      const tip = coin+' · '+(VNAME[v]||v)+' · '+fmtUsd(SZ[ZI])
        + '\nmedian ' + c.med.toFixed(3) + ' bps'
        + (c.fee!=null ? '\ntaker fee ' + c.fee.toFixed(2) + ' bps  ->  with fee ' + (c.med+c.fee).toFixed(3) : '')
        + (c.spike2!=null ? '\nspikes over median: ' + c.spike2.toFixed(1) + '% >2x, ' + c.spike5.toFixed(1) + '% >5x' : '')
        + (c.worst!=null ? '\nworst single reading ' + c.worst.toFixed(2) + ' bps (' + c.worst_x + 'x median)' : '')
        + '\np10–p90 ' + (c.p10==null?'—':c.p10.toFixed(2)+' – '+c.p90.toFixed(2))
        + '\nbuy/sell ' + (c.med_buy==null?'—':c.med_buy.toFixed(2)) + ' / ' + (c.med_sell==null?'—':c.med_sell.toFixed(2))
        + '\nfilled ' + (c.fill*100).toFixed(0) + '% of ' + c.n_listed + ' rounds'
        + (ex ? '\n→ excluded from ranking (could not fill the size)' : '');
      h += '<td class="'+cls+'"><div class="cell '+(thin?'thin':(ex?'excl':''))+'" title="'+tip.replace(/"/g,'&quot;')+'" '
         + 'style="background:'+rankColor(rk[v],n)+'">'
         + '<div class="v">'+shown.toFixed(shown<1?2:1)+'<span class="rk"> '+(ex?'':(rk[v]||''))+'</span></div>'
         + (thin ? '<span class="xtag thin">n=' + c.n + '</span>'
                 : ex ? '<span class="xtag">unfilled</span>'
               : '')
         + '</div></td>';
    }
    h += '</tr>';
  }
  return h + '</tbody>';
}

function drawSections(){
  document.getElementById('sections').innerHTML = GROUPS.map(g=>
    '<h2>'+LABEL[g]+' <span class="sm">&mdash; '+coinsOf(g).length+' pairs &middot; '
    + fmtUsd(SZ[ZI])+' order</span></h2>'
    + '<div class="tw"><table>'+pairTable(g)+'</table></div>').join('');
}

function drawVerdict(){
  const s = String(SZ[ZI]);
  let cards = '';
  for(const g of GROUPS){
    const bc = D.by_coin[g], coins = coinsOf(g);
    let sum=0, n=0, tot=0, unf=0, na=0;
    for(const c of coins){
      const r = rankRow(bc[c], s), rk = r[0], k = r[1];
      if(rk['grvt']){ sum += rk['grvt']; n++; tot += k; }
      const cc = bc[c]['grvt'] && bc[c]['grvt'][s];
      if(!cc || cc.med==null) na++; else if(!cc.rankable) unf++;
    }
    const avg = n ? (sum/n) : null, of = n ? Math.round(tot/n) : 0;
    const col = !avg ? '#fca5a5' : (avg<=3?'#86efac':(avg<=of/2?'#fcd34d':'#fca5a5'));
    cards += '<div class="rankcard"><div class="sz">'+LABEL[g]+' &middot; '+fmtUsd(SZ[ZI])+'</div>'
      + '<div class="rk" style="color:'+col+'">'+(avg?('#'+avg.toFixed(1)):'unranked')
      + '<span class="of">'+(avg?(' of '+of):'')+'</span></div>'
      + '<div class="mv">'+n+' of '+coins.length+' pairs ranked'
      + (unf?' &middot; <span style="color:#fca5a5">'+unf+' unfilled</span>':'')
      + (na?' &middot; '+na+' not listed':'') + '</div></div>';
  }
  document.getElementById('verdict').innerHTML =
      '<div class="vhead">GRVT &mdash; average rank per pair at '+fmtUsd(SZ[ZI])+'</div>'
    + '<div class="rankrow">'+cards+'</div>'
    + '<div class="why">Rank is computed <b>within each pair</b> and then averaged &mdash; never by pooling'
    + ' pairs, because absolute levels differ by orders of magnitude (BTC ~0.01bps vs ADA ~16bps).<br>'
    + 'Cells the book could not fill are marked <b>unfilled</b> and left out of the ranking &mdash;'
    + ' a low number you cannot actually trade is not liquidity.<br>'
    + 'Fees are excluded; add taker fees for real cost.</div>';
}

function drawDist(){
  const t = (COIN==='__ALL__') ? D.scope[DG]['all'].table : (D.by_coin[DG][COIN]||{});
  const s = String(SZ[ZI]), rows = venueOrder(DG, s);
  let lo=Infinity, hi=-Infinity;
  rows.forEach(v=>{ const c=t[v]&&t[v][s]; if(c&&c.p10!=null){ lo=Math.min(lo,c.p10); hi=Math.max(hi,c.p90);} });
  if(!isFinite(lo)){ lo=0; hi=1; }
  const W=320, X = x => ((x-lo)/(hi-lo||1))*W;
  let h = '<thead><tr><th style="text-align:left;position:sticky;left:0;background:#0f172a">Venue</th>'
        + '<th style="text-align:left">p10 &mdash; p90 (bps) &middot; '+fmtUsd(SZ[ZI])+'</th>'
        + '<th>median</th><th>&sigma;</th><th>buy / sell</th></tr></thead><tbody>';
  for(const v of rows){
    const c = t[v] && t[v][s];
    h += '<tr><td class="pn" style="'+(v==='grvt'?'border-left:3px solid #94a3b8':'')+'">'+(VNAME[v]||v)+'</td>';
    if(!c || c.p10==null){ h += '<td colspan="4"><div class="cell na">no data</div></td></tr>'; continue; }
    h += '<td style="padding:8px 12px"><div class="dist" style="width:'+W+'px">'
       + '<div class="whisk" style="left:'+X(c.p10+FEE(c))+'px;width:'+(X(c.p90+FEE(c))-X(c.p10+FEE(c)))+'px"></div>'
       + '<div class="box" style="left:'+X(c.p25+FEE(c))+'px;width:'+Math.max(2,X(c.p75+FEE(c))-X(c.p25+FEE(c)))+'px"></div>'
       + '<div class="med" style="left:'+X(val(c))+'px"></div></div></td>'
       + '<td><div class="cell"><span class="v">'+val(c).toFixed(2)+'</span></div></td>'
      + '<td><div class="cell na">—</div></td>'
       + '<td><div class="cell m" style="font-size:11px;opacity:1">'
       + (c.med_buy==null?'—':c.med_buy.toFixed(2))+' / '+(c.med_sell==null?'—':c.med_sell.toFixed(2))
       + '</div></td></tr>';
  }
  document.getElementById('tblDist').innerHTML = h + '</tbody>';
}

function drawCov(){
  let h = '';
  for(const g of GROUPS){
    const cov = D.coverage[g], coins = coinsOf(g), rows = venueOrder(g, String(SZ[ZI]));
    h += '<thead><tr><th style="text-align:left;position:sticky;left:0;background:#0f172a">'
       + LABEL[g] + '</th>' + coins.map(c=>'<th>'+c+'</th>').join('') + '<th>total</th></tr></thead><tbody>';
    for(const v of rows){
      let n=0;
      const row = coins.map(c=>{ const y=cov[c]&&cov[c][v]; if(y)n++;
        return '<td class="'+(y?'y':'n')+'">'+(y?'●':'·')+'</td>'; }).join('');
      h += '<tr><td class="pn" style="'+(v==='grvt'?'border-left:3px solid #94a3b8':'')+'">'
         + (VNAME[v]||v)+'</td>'+row
         + '<td style="font-weight:700;color:'+(n===coins.length?'#34d399':'#fcd34d')+'">'+n+'</td></tr>';
    }
    h += '</tbody>';
  }
  document.getElementById('tblCov').innerHTML = h;
}

function mkSeg(id, items, cur, on){
  const el = document.getElementById(id);
  el.innerHTML = items.map(function(it){
    return '<button data-k="'+it[0]+'" class="'+(it[0]===cur?'on':'')+'">'+it[1]+'</button>'; }).join('');
  el.querySelectorAll('button').forEach(function(b){
    b.onclick = function(){
      el.querySelectorAll('button').forEach(function(x){ x.classList.toggle('on', x===b); });
      on(b.dataset.k);
    };
  });
}
function refreshCoinSel(){
  const sel = document.getElementById('selCoin'), coins = coinsOf(DG);
  if(coins.indexOf(COIN)<0) COIN = '__ALL__';
  sel.innerHTML = '<option value="__ALL__">All pairs (pooled)</option>'
    + coins.map(function(c){ return '<option value="'+c+'"'+(c===COIN?' selected':'')+'>'+c+'</option>'; }).join('');
  sel.onchange = function(){ COIN = sel.value; drawDist(); };
}
function drawAll(){ drawVerdict(); drawSections(); refreshCoinSel(); drawDist(); drawCov(); }

mkSeg('segZ', SZ.map(function(s,i){ return [String(i), fmtUsd(s)]; }), String(ZI),
      function(k){ ZI = +k; drawAll(); });
mkSeg('segDG', GROUPS.map(function(g){ return [g, LABEL[g]]; }), DG,
      function(k){ DG = k; refreshCoinSel(); drawDist(); });
mkSeg('segFee', [['0','slippage only'], ['1','+ taker fee']], WITHFEE ? '1' : '0',
      function(k){ WITHFEE = (k === '1'); drawFeeNote(); drawAll(); });

/* ★어떤 수수료를 더했는지 보여 준다. 숫자만 바뀌고 근거가 없으면 믿을 수 없다. */
function drawFeeNote(){
  const F = D.meta.fees || {}, asof = D.meta.fee_asof;
  document.getElementById('feeNote').innerHTML = WITHFEE
    ? 'showing <b>slippage + taker fee</b> at the <b>lowest tier, no discounts</b>'
      + (asof ? ' &middot; checked ' + asof : '')
    : 'taker fees are excluded by default &mdash; they vary by tier and promotion, '
      + 'so they are a poor basis for comparison. Turn them on to see what a taker actually pays.';
  const box = document.getElementById('feeTable');
  const keys = Object.keys(F).filter(k => VEN.indexOf(k) >= 0);
  if (!WITHFEE || !keys.length){ box.style.display = 'none'; return; }
  keys.sort((a, b) => F[a] - F[b]);
  box.style.display = '';
  box.innerHTML = '<b>Taker fee added to every figure</b> (bps, lowest tier, no discounts'
    + (asof ? ', checked ' + asof : '') + ')<br>'
    + keys.map(k => (VNAME[k] || k) + ' <b>' + F[k].toFixed(1) + '</b>').join(' &nbsp;&middot;&nbsp; ')
    + '<br><span style="color:#64748b">Your own rate will differ &mdash; volume tiers, '
    + 'token discounts and promotions all move it. That is why the ranking excludes fees by default.</span>';
}
drawFeeNote();
drawAll();
initTrend();
</script></body></html>"""

HTML = (HTML.replace('__NV__', str(len(M['venues'])))
            .replace('__NC__', str(M['coins']))
            .replace('__ROUNDS__', str(M['rounds']))
            .replace('__ROWS__', '{:,}'.format(M['rows']))
            .replace('__SPAN__', '%s → %s' % (M['span'][0][5:16].replace('T', ' '), M['span'][1][11:16]))
            .replace('__SRC__', M['src'])
            .replace('__ORDER__', json.dumps(ORDER))
            .replace('__LABEL__', json.dumps(LABEL))
            .replace('__DATA__', json.dumps(D, ensure_ascii=False, separators=(',', ':')))
            .replace('__HIST__', json.dumps(HIST, ensure_ascii=False, separators=(',', ':')))
            .replace('__EVERY__', _every)
            .replace('__WIN__', str(M.get('window_h', 24)))
            .replace('__SITE__', SITE)
            .replace('__MINN__', str(M.get('min_n', 100)))
            .replace('__MAXSHORT__', '%g' % (M.get('max_short', .05) * 100)))
def _syntax_gate(html):
    """★<script> 안이 파싱되는지 확인한다.

    브라우저는 스크립트 파싱에 실패하면 **오류를 내지 않고 조용히 통째로 버린다.**
    그래서 화면이 텅 비는데 콘솔은 깨끗하다. 실제로 두 번 당했다 —
    한 번은 지도(13MB), 한 번은 이 리포트(따옴표 안의 줄바꿈).
    파일을 쓰기 전에 여기서 막는다.
    """
    import re
    import shutil
    import subprocess
    import tempfile
    blocks = re.findall(r'<script>(.*?)</script>', html, re.S)
    if not blocks:
        print('★<script> 블록이 없다'); sys.exit(1)

    # ★node 가 없는 곳(수집 서버 등)에서는 게이트를 건너뛴다.
    #   게이트는 **사고를 막으려고** 있는 것이지 파이프라인을 멈추려고 있는 게 아니다.
    #   실제로 여기서 죽어 9시간 동안 리포트가 안 올라갔다.
    #   대신 조용히 넘어가지 않는다 — 검사 못 했다는 사실을 남긴다.
    if not shutil.which('node'):
        print('★구문 게이트 건너뜀 — node 가 없다. 배포 전에 반드시 로컬에서 확인할 것')
        return
    for i, b in enumerate(blocks):
        f = pathlib.Path(tempfile.gettempdir()) / ('_gate_%d.js' % i)
        f.write_text(b, encoding='utf-8')
        r = subprocess.run(['node', '--check', str(f)], capture_output=True,
                           text=True, encoding='utf-8', errors='replace')
        if r.returncode:
            print('★구문 게이트 실패 — 파일을 쓰지 않는다')
            print((r.stderr or '')[:700])
            sys.exit(1)
    print('★구문 게이트 통과 (%d블록 · %.0f KB)'
          % (len(blocks), sum(len(b) for b in blocks) / 1e3))


_syntax_gate(HTML)
OUT.write_text(HTML, encoding='utf-8')
print('-> %s (%.2f MB)' % (OUT, OUT.stat().st_size / 1e6))
