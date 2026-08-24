# -*- coding: utf-8 -*-
"""★4시간 수집 결과 집계 — "GRVT 는 유동성이 좋은가"에 정직하게 답하기 위해.

★걷어내야 할 착시 (실측으로 확인한 것 + GPT 선회부 runs_consult_html.md)
 1. **커버리지 착시** — MEXC 는 RWA 10종목 중 2개만 상장. 없는 종목이 평균에서 빠져
    "MEXC 압도적 1위"가 된다. → 공통 상장 종목만 비교하는 판을 따로 만든다.
 2. **미체결 착시** — 채운 라운드만 평균 내면, 그 규모를 못 사는 곳이 최고로 보인다.
    → 슬리피지 옆에 **체결 성공률**을 항상 같이 둔다. 두 개를 나란히 봐야 한다.
 3. **한 번 재기 착시** — aster·kucoin 은 라운드마다 30~80bps 출렁인다.
    → 중위만이 아니라 p10/p25/p75/p90 과 표준편차를 낸다.
 4. **표본 착시** — 유효 라운드가 적은 칸을 같은 신뢰도로 보여주면 안 된다. → N 을 싣는다.
 5. **방향 편향** — buy 만 보면 한쪽만 본다. → buy·sell 을 따로도 낸다.

산출: _agg_liquidity.json  (HTML 이 이걸 읽어 그린다)
"""
import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = pathlib.Path(__file__).resolve().parent
RECENT = ROOT / 'data' / 'recent'
OUT = ROOT / 'data' / 'agg_latest.json'
MIN_N = 100          # ★이보다 표본이 적으면 순위에서 뺀다
MAX_SHORT = 0.05     # ★못 채운 비율이 이보다 크면 순위에서 뺀다
WINDOW_H = 24        # 최근 이만큼만 본다

# ★최근 24시간 원시를 전부 읽어 하나로 본다. 시간별 파일이 나뉘어 있을 뿐
#   판단 단위는 "최근 24시간" 하나다.
files = sorted(RECENT.glob('*.csv.gz'))
if not files:
    print('★%s 에 원시가 없다. collect.py 를 먼저 돌려야 한다.' % RECENT)
    sys.exit(1)
print('원시 %d개 읽는 중… %.1fMB' % (files.__len__(),
                                 sum(f.stat().st_size for f in files) / 1e6))
parts = []
for i, f in enumerate(files):
    p = pd.read_csv(f, low_memory=False)
    # 파일마다 round 가 1부터 다시 시작한다 → 겹치지 않게 밀어 준다
    p['round'] = p['round'] + i * 100000
    parts.append(p)
df = pd.concat(parts, ignore_index=True)

# ★24시간을 넘는 관측은 잘라낸다. 파일 단위로만 지우면 경계가 흐려진다.
df['_t'] = pd.to_datetime(df.ts, errors='coerce')
cut = df['_t'].max() - pd.Timedelta(hours=WINDOW_H)
before = len(df)
df = df[df['_t'] >= cut].drop(columns=['_t'])
if len(df) < before:
    print('   24시간 밖 %s행 잘라냄' % '{:,}'.format(before - len(df)))
print('%s행 · 라운드 %d · 종목 %d' % ('{:,}'.format(len(df)), df['round'].nunique(), df.coin.nunique()))

df['ok'] = df['status'] == 'ok'
df['short'] = df['status'].isin(['book_short', 'band_short'])
df['nobook'] = df['status'] == 'no_book'
main = df[df.venue != 'hyperliquid_raw'].copy()
VENUES = sorted(main.venue.unique())
SIZES = [int(s) for s in sorted(main.usd_size.unique())]


def cell(d):
    """한 칸 = 슬리피지 분포 + 체결 성공률 + 흔들림 + 표본수.
    ★체결 성공률은 **그 종목이 상장된 관측**만 분모로 한다(미상장은 빼야 공정하다)."""
    listed = d[~d.nobook]
    if not len(listed):
        return None
    okd = listed[listed.ok]
    n = len(okd)
    fill = float(okd.shape[0] / listed.shape[0])
    out = {'n': int(n), 'n_listed': int(len(listed)), 'fill': round(fill, 4)}
    if n:
        q = okd.slippage_bps.quantile([.1, .25, .5, .75, .9])
        out.update({'p10': round(float(q[.1]), 3), 'p25': round(float(q[.25]), 3),
                    'med': round(float(q[.5]), 3), 'p75': round(float(q[.75]), 3),
                    'p90': round(float(q[.9]), 3)})
        pr = okd.groupby('round').slippage_bps.median()
        out['sd'] = round(float(pr.std()), 3) if len(pr) > 2 else None
        for side in ('buy', 'sell'):
            s = okd[okd.side == side].slippage_bps
            out['med_' + side] = round(float(s.median()), 3) if len(s) else None
    # ★순위에 넣어도 되는 칸인가 — 표본이 적거나 자주 못 채우면 뺀다
    out['rankable'] = bool(n >= MIN_N and fill >= (1 - MAX_SHORT))
    return out


def table(d):
    return {v: {str(s): cell(d[(d.venue == v) & (d.usd_size == s)]) for s in SIZES}
            for v in VENUES}


res = {'meta': {
    'src': '%d files / recent %dh' % (len(files), WINDOW_H),
    'built_at': pd.Timestamp.utcnow().isoformat(timespec='seconds'),
    'rows': int(len(df)), 'rounds': int(df['round'].nunique()),
    'coins': int(df.coin.nunique()), 'venues': VENUES, 'sizes': SIZES,
    'span': [str(df.ts.min()), str(df.ts.max())],
    'min_n': MIN_N, 'max_short': MAX_SHORT,
}}

# ── 상장 여부 ────────────────────────────────────────────────────────────────
cov = main[~main.nobook].groupby(['group', 'coin', 'venue']).size().unstack(fill_value=0)
res['coverage'] = {}
for (g, coin), row in cov.iterrows():
    res['coverage'].setdefault(g, {})[coin] = {v: bool(row.get(v, 0) > 0) for v in VENUES}

# ── 두 판: 전체 상장분 / 공통 상장분 ────────────────────────────────────────
res['scope'] = {}
for g in ('MAJOR', 'RWA'):
    d0 = main[main.group == g]
    listed = d0[~d0.nobook].groupby(['coin', 'venue']).size().unstack(fill_value=0)
    common = sorted([c for c in listed.index if (listed.loc[c] > 0).all()])
    res['scope'][g] = {
        'all': {'coins': sorted(d0.coin.unique()), 'table': table(d0)},
        'common': {'coins': common, 'table': table(d0[d0.coin.isin(common)])},
    }
    print('★%s — 전체 %d종목 · 공통 상장 %d종목 %s'
          % (g, d0.coin.nunique(), len(common), common))

# ── 종목별 ──────────────────────────────────────────────────────────────────
res['by_coin'] = {}
for g in ('MAJOR', 'RWA'):
    d0 = main[main.group == g]
    res['by_coin'][g] = {c: table(d0[d0.coin == c]) for c in sorted(d0.coin.unique())}

# ── 책 깊이 ─────────────────────────────────────────────────────────────────
bk = main[main.book_usd_bid.notna()].groupby(['group', 'venue'])[
    ['book_usd_bid', 'book_usd_ask']].median()
res['book'] = {}
for (g, v), row in bk.iterrows():
    res['book'].setdefault(g, {})[v] = {'bid': int(row.book_usd_bid), 'ask': int(row.book_usd_ask)}

# ── hyperliquid raw vs nSigFigs=4 ──────────────────────────────────────────
res['hl_compare'] = {v: {str(s): cell(df[(df.venue == v) & (df.usd_size == s)]) for s in SIZES}
                     for v in ('hyperliquid', 'hyperliquid_raw')}

# ── GRVT 순위 (공통 상장 기준, 순위 자격 있는 칸만) ─────────────────────────
res['grvt_rank'] = {}
for g in ('MAJOR', 'RWA'):
    t = res['scope'][g]['common']['table']
    res['grvt_rank'][g] = {}
    for s in SIZES:
        vals = [(v, t[v][str(s)]['med']) for v in VENUES
                if t[v][str(s)] and t[v][str(s)].get('rankable') and t[v][str(s)].get('med') is not None]
        vals.sort(key=lambda x: x[1])
        r = next((i for i, (v, _) in enumerate(vals, 1) if v == 'grvt'), None)
        me = t['grvt'][str(s)] or {}
        res['grvt_rank'][g][str(s)] = {
            'rank': r, 'of': len(vals), 'med': me.get('med'), 'fill': me.get('fill'),
            'rankable': me.get('rankable'),
            'best': vals[0] if vals else None, 'worst': vals[-1] if vals else None}
    print('★GRVT(%s, 공통상장): %s'
          % (g, {k: '%s/%s' % (v['rank'], v['of']) for k, v in res['grvt_rank'][g].items()}))

OUT.write_text(json.dumps(res, ensure_ascii=False), encoding='utf-8')
print('\n-> %s (%.2f MB)' % (OUT, OUT.stat().st_size / 1e6))
