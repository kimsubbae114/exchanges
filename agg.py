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
# ★호출 실패는 '미상장'이 아니다. 섞으면 차단당한 거래소가 조용히 빠져
#   화면이 "그 거래소는 상장이 없다"고 거짓말을 한다.
df['apifail'] = df['status'] == 'api_fail'
main = df[df.venue != 'hyperliquid_raw'].copy()
VENUES = sorted(main.venue.unique())
SIZES = [int(s) for s in sorted(main.usd_size.unique())]


# ★수수료는 수집 코드가 들고 있는 현재값을 그대로 쓴다 — 두 군데 적으면 어긋난다
try:
    import benchmark_major_rwa as _B
    _B.load_fees(log=lambda *a: None)          # 공개 API 로 받을 수 있는 건 갱신
    FEE_NOW = {k: round(v * 1e4, 3) for k, v in _B.FEES.items()}
    FEE_ASOF = getattr(_B, 'FEE_ASOF', None)
    print('수수료 기준 %s — %s' % (FEE_ASOF,
          ' · '.join('%s %.1f' % (k, v) for k, v in sorted(FEE_NOW.items(), key=lambda x: x[1]))))
except Exception as _e:
    print('★수수료표를 못 읽었다 (%s) — 원시에 박힌 값을 쓴다' % _e)
    FEE_NOW, FEE_ASOF = {}, None


def v_name(d):
    """이 칸이 어느 거래소인가. hyperliquid_raw 는 hyperliquid 와 같은 수수료다."""
    if 'venue' not in d or not len(d):
        return None
    return str(d.venue.iloc[0]).replace('_raw', '')


def cell(d):
    """한 칸 = 슬리피지 분포 + 체결 성공률 + 흔들림 + 표본수.
    ★체결 성공률은 **그 종목이 상장된 관측**만 분모로 한다(미상장은 빼야 공정하다)."""
    # 호출이 실패한 관측은 분모에서 뺀다 — 체결 성공률을 깎으면 안 된다
    fails = int(d.apifail.sum()) if 'apifail' in d else 0
    listed = d[~d.nobook & ~d.get('apifail', False)]
    if not len(listed):
        # 전부 호출 실패였다면 그 사실을 남긴다
        return {'n': 0, 'api_fail': fails, 'blocked': fails > 0} if fails else None
    okd = listed[listed.ok]
    n = len(okd)
    fill = float(okd.shape[0] / listed.shape[0])
    out = {'n': int(n), 'n_listed': int(len(listed)), 'fill': round(fill, 4),
           'api_fail': fails}
    if n:
        q = okd.slippage_bps.quantile([.1, .25, .5, .75, .9])
        out.update({'p10': round(float(q[.1]), 3), 'p25': round(float(q[.25]), 3),
                    'med': round(float(q[.5]), 3), 'p75': round(float(q[.75]), 3),
                    'p90': round(float(q[.9]), 3)})
        pr = okd.groupby('round').slippage_bps.median()
        out['sd'] = round(float(pr.std()), 3) if len(pr) > 2 else None

        # ★수수료 — **원시에 박힌 값이 아니라 지금 값을 쓴다.**
        #   슬리피지는 24시간 동안 잰 과거 측정치지만, 수수료는 "지금 내는 돈"이다.
        #   과거 평균을 낼 이유가 없다. 실제로 원시에는 옛 값(hyperliquid 3.5 등)이
        #   박혀 있어, 그대로 쓰면 고쳐 놓고도 화면에 옛 숫자가 나온다.
        out['fee'] = FEE_NOW.get(v_name(d), None)

        # ★튐(스파이크) — 중위만 보면 "가끔 크게 나쁜 곳"과 "늘 고른 곳"이 같아 보인다.
        #   기준은 **그 칸의 중위값**이다. 절대 bps 로 자르면 BTC 는 영원히 안 튀고
        #   ADA 는 늘 튀는 것으로 보인다.
        med = float(q[.5])
        if med > 0:
            ratio = okd.slippage_bps / med
            out['spike2'] = round(float((ratio >= 2).mean()) * 100, 2)   # 중위의 2배 이상 비율(%)
            out['spike5'] = round(float((ratio >= 5).mean()) * 100, 2)   # 5배 이상
            out['worst'] = round(float(okd.slippage_bps.max()), 3)       # 최악 한 번
            out['worst_x'] = round(float(okd.slippage_bps.max() / med), 1)  # 중위의 몇 배
        else:
            out['spike2'] = out['spike5'] = out['worst'] = out['worst_x'] = None
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
    'window_h': WINDOW_H,
    # ★측정 기준 — 공개 자료이므로 화면에 그대로 밝힌다
    'interval_sec': None,   # 아래에서 실측해 채운다
    # ★어떤 수수료로 계산했는지 화면에 밝힌다. 안 보이면 검증할 수 없다.
    'fees': FEE_NOW, 'fee_asof': FEE_ASOF,
}}

# 라운드 사이 실제 간격을 재서 적는다. "5분마다"라고 적어 놓고 실제로 다르면 거짓말이 된다.
_t = pd.to_datetime(df.groupby('round').ts.min(), errors='coerce').sort_values()
if len(_t) > 2:
    _gap = _t.diff().dt.total_seconds().dropna()
    _gap = _gap[(_gap > 0) & (_gap < 3600)]
    if len(_gap):
        res['meta']['interval_sec'] = int(round(float(_gap.median())))

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

# ── 스파이크 (튐) ───────────────────────────────────────────────────────────
# ★"평균은 좋은데 가끔 크게 당한다"를 드러내는 판. 중위만 보면 이게 안 보인다.
#
# 재는 법
#  · 기준선 = 그 칸(거래소×종목×사이즈)의 **중위값**. 절대 bps 로 자르면
#    BTC 는 영원히 안 튀고 ADA 는 늘 튀는 것으로 보인다.
#  · 빈도 = 기준선의 2배·3배·5배를 넘은 관측의 비율(%)
#  · 크기 = p99 배수와 최대 배수, **그리고 그때의 절대 bps**
#
# ★배수만 보면 과장된다 — GRVT BTC 는 중위가 0.0064bps 라 2.5bps 만 나와도
#   "398배"가 된다. 실제로 문 손실은 2.5bps 다. 그래서 절대값을 반드시 같이 낸다.

sp = main[main.ok].copy()
if len(sp):
    base = sp.groupby(['venue', 'coin', 'usd_size']).slippage_bps.transform('median')
    sp['base'] = base
    sp['x'] = sp.slippage_bps / sp.base.replace(0, float('nan'))
    # ★★기준선을 0 으로 맞추고 **초과분(bps)** 을 본다 — 이것이 주 지표다.
    #   "평소보다 얼마나 더 물었나"는 종목·거래소가 달라도 같은 단위(bps)라
    #   한 그래프에 올릴 수 있고, 실제 비용을 그대로 반영한다.
    #
    #   배수(x)로만 보면 기준선이 작은 칸이 과장된다(GRVT BTC 는 0.006bps 라 398배).
    #   진폭을 그 칸의 평소 진폭으로 나누는 방법도 시험했는데, 늘 출렁이는 거래소는
    #   분모가 커져 "정상"이 되어 버려 **변별력이 사라졌다**(CV 0.50 -> 0.10).
    #   초과분(bps)은 그 함정이 없다(빈도 폭 18.9%p, p99 CV 1.20).
    sp['ex'] = (sp.slippage_bps - sp.base).clip(lower=0)

    def spike_block(d):
        if not len(d):
            return None
        out = {
            'n': int(len(d)),
            # ★주 지표 — 기준선 대비 초과분(bps)
            'e2': round(float((d.ex >= 2).mean()) * 100, 2),    # 2bps 넘게 더 문 비율
            'e5': round(float((d.ex >= 5).mean()) * 100, 2),
            'e10': round(float((d.ex >= 10).mean()) * 100, 2),
            'ex95': round(float(d.ex.quantile(.95)), 2),
            'ex99': round(float(d.ex.quantile(.99)), 2),
            'exmax': round(float(d.ex.max()), 1),
            # 스파이크일 때 평균적으로 얼마나 더 물었나 (2bps 초과 건들의 평균)
            'exmean': round(float(d.ex[d.ex >= 2].mean()), 2) if (d.ex >= 2).any() else 0.0,
            'medbps': round(float(d.slippage_bps.median()), 3),
            # 보조 — 배수. 참고용으로만 남긴다(기준선이 작으면 과장된다)
            'f2': round(float((d.x >= 2).mean()) * 100, 2) if d.x.notna().any() else None,
            'p99x': round(float(d.x.quantile(.99)), 1) if d.x.notna().any() else None,
        }
        return out

    res['spike'] = {'by_venue': {}, 'by_group': {}, 'by_size': {}}
    for v, d0 in sp.groupby('venue'):
        res['spike']['by_venue'][v] = spike_block(d0)
    for (v, g), d0 in sp.groupby(['venue', 'group']):
        res['spike']['by_group'].setdefault(g, {})[v] = spike_block(d0)
    for (v, z), d0 in sp.groupby(['venue', 'usd_size']):
        res['spike']['by_size'].setdefault(str(int(z)), {})[v] = spike_block(d0)

    print('★스파이크 — 기준선 대비 2bps 넘게 더 문 비율(%) 낮은 순')
    for v, b in sorted(res['spike']['by_venue'].items(), key=lambda x: x[1]['e2']):
        print('   %-12s 2bps↑ %5.2f%% · 5bps↑ %5.2f%% · p99 초과 %7.2f bps · 최악 %6.1f bps'
              % (v, b['e2'], b['e5'], b['ex99'], b['exmax']))
else:
    res['spike'] = None


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
