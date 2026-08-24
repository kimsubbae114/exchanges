# -*- coding: utf-8 -*-
"""메이저 CEX 5 + 퍼프 DEX 5 × (메이저 10 · RWA 10) 유동성 벤치마크.

기존 benchmark_tool_kimminsu_all.py 의 틀을 따르되, 거래소를 넓히고
★**계약 단위 환산**을 넣었다. 이게 이 파일의 핵심이다.

──────────────────────────────────────────────────────────────────────────────
★탐색으로 확인한 사실 (2026-08-18, _probe_venues.py / _probe_symbols.py / _probe_rwa.py)

  거래소        공개 오더북   최대 깊이        수량 단위
  binance       O            1000 레벨       코인 수량 그대로
  bybit         O             500 레벨       코인 수량 그대로
  okx           O            5000 레벨       ★계약 수 × ctVal (BTC 0.01 · ETH 0.1 · SOL 1)
  mexc          O            1500 레벨       ★계약 수 × contractSize (BTC 0.0001)
  kucoin        O            1000 레벨       ★계약 수 × multiplier (BTC 0.001)
  grvt          O             100 레벨       코인 수량
  hyperliquid   O            ★20 레벨만      코인 수량 (nSigFigs 로 가격 묶음 폭 조절)
  aster         O             500 레벨       코인 수량
  lighter       O             주문 단위       코인 수량 (★같은 가격끼리 합쳐야 한다)
  extended      O            4000+ 레벨      코인 수량

  ★단위 검증 — BTC 최우선 호가를 달러로 환산해 서로 맞는지 확인했다:
     okx $731k · kucoin $117k · mexc $4,750k · binance $1,261k → 전부 같은 자릿수. 단위가 맞다.
     환산을 빼먹으면 okx 는 100배, kucoin 은 1000배, mexc 는 10000배 부풀어 보인다.

  ★하이퍼리퀴드는 **항상 20레벨**이다. nSigFigs 가 깊이를 늘리는 게 아니라
     가격을 뭉쳐 담는 폭을 넓힌다. 20레벨이 담는 달러(실측):
        BTC  raw 4.6M / nSig4 64.9M      SOL  raw 315k / nSig4 7.9M
        ETH  raw 14.1M / nSig4 70.5M     HYPE raw 132k / nSig4 2.5M
     → $200k 주문을 재려면 nSigFigs=4 가 필요하다. 대신 가격이 뭉쳐
       **슬리피지가 과소평가**될 수 있다. 그래서 두 판을 다 받아 둘 다 기록한다.
──────────────────────────────────────────────────────────────────────────────

★거짓말하지 않기 위한 규칙
 1. 책이 주문을 못 채우면 **슬리피지를 만들어내지 않는다** — None 으로 두고 'book_short' 로 표시한다.
    (얕은 책에서 마지막 호가로 나머지를 채우면 유동성이 있는 것처럼 보인다)
 2. 거래소마다 **깊이 상한이 다르다**. 그래서 '책 전체 달러'를 같이 싣는다 —
    슬리피지가 좋아 보여도 책이 얕으면 그건 못 채운다는 뜻이다.
 3. 수수료는 **비교에서 뺀다**(등급마다 다르다). 필요하면 FEES 로 따로 본다.
 4. ★가격보호밴드(±10%) 밖은 안 채운다 — 거래소가 실제로 거부하는 구간이다.
 5. 소비한 레벨 수를 남긴다 — 깊이 상한에 닿았는지 봐야 얕아서인지 없어서인지 갈린다.

★아직 반영하지 못한 것 (GPT 사후 레드팀 runs_consult_bench.md — 알고도 안 한 것들)
 · **스텝사이즈·최소주문금액** 반올림 — 레벨별 단위를 무시해 과대체결 가능. 영향은 작을 것이나 미측정.
 · **스테일 호가·유령 유동성** — 체결 전에 사라지는 물량을 못 거른다
   (호가 age 를 주는 거래소가 일부뿐이라 공통 기준을 못 만들었다).
 · **DEX 체결지연** — 시퀀서·블록 지연 동안의 가격 이동은 스냅샷에 안 잡힌다.
 · **스테이블 디페그** — USDT/USD 를 1:1 로 본다. extended 는 USD 견적이라 quote_ccy 로 표시만 한다.
 · **RWA 장시간 외 왜곡** — 미국장 마감 중에는 인덱스·리스크룰 차이가 순위로 번질 수 있다.
   → RWA 는 **미국 정규장 시간대에도 한 번** 재서 비교해야 한다.
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings()
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
CEX = ['binance', 'bybit', 'okx', 'mexc', 'kucoin']
DEX = ['grvt', 'hyperliquid', 'aster', 'lighter', 'extended']
VENUES = CEX + DEX

# 시총 상위 · 10곳 전부에 상장된 것만 골랐다(탐색으로 확인)
MAJOR = ['BTC', 'ETH', 'SOL', 'XRP', 'BNB', 'DOGE', 'ADA', 'LINK', 'AVAX', 'SUI']

# 주식·금 퍼프. 거래소별 커버리지가 다르므로 **넓게 걸리는 것** 위주로 골랐다.
RWA = ['TSLA', 'NVDA', 'AAPL', 'MSTR', 'COIN', 'META', 'PLTR', 'HOOD', 'GOOGL', 'XAU']

GROUPS = {'MAJOR': MAJOR, 'RWA': RWA}

# ★모든 자산을 **같은 달러 사다리**로 잰다. 그래야 메이저와 RWA 를 나란히 놓고 볼 수 있다.
#   못 채우는 것도 정보다 — RWA 에서 $1M 이 book_short 로 뜨면 그게 곧 "그만큼은 못 산다"는 뜻이다.
#   (자산군마다 다른 사다리를 쓰면 표는 예뻐지지만 서로 비교가 안 된다)
#   ★실측 참고: BTC 는 $100k 까지 최우선 1레벨에서 채워져 거래소 간 차이가 0.01bps 로 뭉갠다.
#     변별력은 $500k 부터 생긴다($1M 에서 0.02~1.76bps, $5M 에서 1.02~6.08bps).
USD_SIZES = [10_000, 50_000, 100_000, 500_000, 1_000_000]
USD_SIZES_EXTRA = [5_000_000]        # --big 을 주면 여기까지 잰다(메이저 변별용)

# 참고용 taker 수수료(등급·프로모션에 따라 달라진다 — 비교 순위에는 쓰지 않는다)
FEES = {'binance': 0.00045, 'bybit': 0.00055, 'okx': 0.0005, 'mexc': 0.0002,
        'kucoin': 0.0006, 'grvt': 0.00045, 'hyperliquid': 0.00035,
        'aster': 0.00035, 'lighter': 0.0, 'extended': 0.00025}

UA = {'User-Agent': 'liquidity-benchmark/1.0'}
TIMEOUT = 10
S = requests.Session()
S.verify = False
S.headers.update(UA)


# ══════════════════════════════════════════════════════════════════════════════
# 심볼 표기 — 거래소마다 다르다
# ══════════════════════════════════════════════════════════════════════════════
# ★예외만 적는다. 나머지는 규칙으로 만든다.
SYMBOL_OVERRIDE = {
    'kucoin':   {'BTC': 'XBT', 'XAU': 'XAUT'},          # kucoin 은 BTC 가 XBT, 금은 XAUT
    'mexc':     {'AAPL': 'AAPLSTOCK'},                  # mexc 주식은 접미사 STOCK
    'extended': {'TSLA': 'TSLA_24_5', 'NVDA': 'NVDA_24_5', 'AAPL': 'AAPL_24_5'},
}


def sym(venue, coin):
    c = SYMBOL_OVERRIDE.get(venue, {}).get(coin, coin)
    return {
        'binance':     lambda x: x + 'USDT',
        'bybit':       lambda x: x + 'USDT',
        'okx':         lambda x: x + '-USDT-SWAP',
        'mexc':        lambda x: x + '_USDT',
        'kucoin':      lambda x: x + 'USDTM',
        'grvt':        lambda x: x + '_USDT_Perp',
        'hyperliquid': lambda x: x,
        'aster':       lambda x: x + 'USDT',
        'lighter':     lambda x: x,
        'extended':    lambda x: x + '-USD',
    }[venue](c)


# ══════════════════════════════════════════════════════════════════════════════
# ★계약 크기 — 이걸 안 곱하면 유동성이 수백~수만 배 부풀어 보인다
# ══════════════════════════════════════════════════════════════════════════════
_CT = {}          # (venue, symbol) -> 곱할 값
_LIGHTER_MKT = {}  # symbol -> market_id


def load_contract_sizes(log=print):
    log('★계약 크기 불러오는 중 (안 곱하면 okx 100배 · kucoin 1000배 · mexc 10000배 어긋난다)')
    try:
        d = S.get('https://www.okx.com/api/v5/public/instruments',
                  params={'instType': 'SWAP'}, timeout=20).json()['data']
        for i in d:
            _CT[('okx', i['instId'])] = float(i.get('ctVal') or 1) * float(i.get('ctMult') or 1)
        log('   okx    %d개' % sum(1 for k in _CT if k[0] == 'okx'))
    except Exception as e:
        log('   okx    ★실패 %s — 계산이 틀어지므로 okx 를 뺀다' % e)
    try:
        d = S.get('https://api-futures.kucoin.com/api/v1/contracts/active', timeout=20).json()['data']
        for i in d:
            _CT[('kucoin', i['symbol'])] = float(i.get('multiplier') or 1)
        log('   kucoin %d개' % sum(1 for k in _CT if k[0] == 'kucoin'))
    except Exception as e:
        log('   kucoin ★실패 %s' % e)
    try:
        d = S.get('https://contract.mexc.com/api/v1/contract/detail', timeout=20).json()['data']
        for i in d:
            _CT[('mexc', i['symbol'])] = float(i.get('contractSize') or 1)
        log('   mexc   %d개' % sum(1 for k in _CT if k[0] == 'mexc'))
    except Exception as e:
        log('   mexc   ★실패 %s' % e)
    try:
        d = S.get('https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails', timeout=20).json()
        for x in d.get('order_book_details', []):
            if x.get('symbol'):
                _LIGHTER_MKT[x['symbol']] = x['market_id']
        log('   lighter %d개 마켓' % len(_LIGHTER_MKT))
    except Exception as e:
        log('   lighter ★실패 %s' % e)


def ct(venue, symbol):
    return _CT.get((venue, symbol), 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# 오더북 — 전부 {'bids': [[가격, **코인 수량**], …], 'asks': …} 로 통일한다
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# ★레이트리밋 — 반복 수집에서 밴을 맞지 않는 게 데이터보다 먼저다
# ══════════════════════════════════════════════════════════════════════════════
#   한 라운드 = 20종목 × 10거래소 = 200요청. 종목을 순차로 돌므로
#   **거래소 하나당 라운드당 20요청**이다. 종목 간 PACE 초를 쉬면
#   거래소당 20 / (20×PACE) req/s 가 된다. PACE=2 면 0.5 req/s —
#   가장 빡빡한 okx books-full(10req/2s)의 10분의 1이다.
#   ★그래도 429/418 이 오면 즉시 늦춘다. 코드를 세어 두고 화면에 띄운다.
PACE_SEC = 2.0          # 종목과 종목 사이 쉬는 시간
_RATE = {'429': 0, '418': 0, '5xx': 0, 'other': 0}
_BACKOFF = {'mult': 1.0}


def _ok(r):
    """★막힘 신호를 세어 둔다 — 조용히 지나가면 데이터가 빈 채로 쌓인다."""
    c = r.status_code
    if c == 200:
        return True
    if c == 429:
        _RATE['429'] += 1
        _BACKOFF['mult'] = min(8.0, _BACKOFF['mult'] * 1.5)   # ★즉시 늦춘다
    elif c == 418:
        _RATE['418'] += 1
        _BACKOFF['mult'] = min(16.0, _BACKOFF['mult'] * 2.0)  # ★밴 직전이다
    elif 500 <= c < 600:
        _RATE['5xx'] += 1
    else:
        _RATE['other'] += 1
    return False


def book_binance(c):
    s = sym('binance', c)
    r = S.get('https://fapi.binance.com/fapi/v1/depth',
              params={'symbol': s, 'limit': 1000}, timeout=TIMEOUT)
    if not _ok(r):
        return None
    d = r.json()
    return {'bids': [[float(p), float(q)] for p, q in d.get('bids', [])],
            'asks': [[float(p), float(q)] for p, q in d.get('asks', [])]}


def book_bybit(c):
    s = sym('bybit', c)
    r = S.get('https://api.bybit.com/v5/market/orderbook',
              params={'category': 'linear', 'symbol': s, 'limit': 500}, timeout=TIMEOUT)
    if not _ok(r):
        return None
    d = (r.json().get('result') or {})
    return {'bids': [[float(p), float(q)] for p, q in d.get('b', [])],
            'asks': [[float(p), float(q)] for p, q in d.get('a', [])]}


def book_okx(c):
    """★books-full 은 5000레벨을 준다. 수량은 **계약 수**라 ctVal 을 곱한다.
       호가 원소가 4개다: [가격, 수량, 0, 주문수] — 앞 두 개만 쓴다."""
    s = sym('okx', c)
    m = ct('okx', s)
    r = S.get('https://www.okx.com/api/v5/market/books-full',
              params={'instId': s, 'sz': 5000}, timeout=TIMEOUT)
    if not _ok(r):
        return None
    d = (r.json().get('data') or [{}])[0]
    if not d.get('bids'):
        return None
    return {'bids': [[float(x[0]), float(x[1]) * m] for x in d['bids']],
            'asks': [[float(x[0]), float(x[1]) * m] for x in d.get('asks', [])]}


def book_mexc(c):
    s = sym('mexc', c)
    m = ct('mexc', s)
    r = S.get('https://contract.mexc.com/api/v1/contract/depth/%s' % s, timeout=TIMEOUT)
    if not _ok(r):
        return None
    d = (r.json().get('data') or {})
    if not d.get('bids'):
        return None
    return {'bids': [[float(x[0]), float(x[1]) * m] for x in d['bids']],
            'asks': [[float(x[0]), float(x[1]) * m] for x in d.get('asks', [])]}


def book_kucoin(c):
    s = sym('kucoin', c)
    m = ct('kucoin', s)
    r = S.get('https://api-futures.kucoin.com/api/v1/level2/snapshot',
              params={'symbol': s}, timeout=TIMEOUT)
    if not _ok(r):
        return None
    d = (r.json().get('data') or {})
    if not d.get('bids'):
        return None
    return {'bids': [[float(x[0]), float(x[1]) * m] for x in d['bids']],
            'asks': [[float(x[0]), float(x[1]) * m] for x in d.get('asks', [])]}


def book_grvt(c):
    r = S.post('https://market-data.grvt.io/full/v1/book',
               json={'instrument': sym('grvt', c), 'depth': 100}, timeout=TIMEOUT)
    if not _ok(r):
        return None
    d = (r.json().get('result') or {})
    if not d.get('bids'):
        return None
    return {'bids': [[float(l['price']), float(l['size'])] for l in d['bids']],
            'asks': [[float(l['price']), float(l['size'])] for l in d.get('asks', [])]}


# ★하이퍼리퀴드는 **주식·금이 메인 선물에 없다**. 빌더 DEX `xyz` 에 있다(실측).
#   메인으로 조회하면 RWA 가 전부 no_book 이 된다 — 실제로 그렇게 나왔다.
_HL_XYZ_ONLY = {'TSLA', 'NVDA', 'AAPL', 'MSTR', 'COIN', 'META', 'PLTR', 'HOOD',
                'GOOGL', 'AMZN', 'MSFT', 'INTC', 'GOLD', 'SILVER'}


def hl_coin(c):
    """하이퍼리퀴드에서 이 종목을 뭐라고 부르나."""
    if c in _HL_XYZ_ONLY:
        return 'xyz:' + c
    if c == 'XAU':
        return 'xyz:GOLD'          # ★금은 xyz 에서 GOLD 다
    if c == 'XAG':
        return 'xyz:SILVER'
    return c


def book_hyperliquid(c, nsig=4):
    """★20레벨만 온다. nsig 로 가격 묶음 폭을 넓혀 큰 주문을 담는다.
       대신 가격이 뭉쳐 슬리피지가 과소평가될 수 있다 — 그래서 raw 판도 따로 받는다."""
    q = {'type': 'l2Book', 'coin': hl_coin(c)}
    if nsig:
        q['nSigFigs'] = nsig
    r = S.post('https://api.hyperliquid.xyz/info', json=q, timeout=TIMEOUT)
    if not _ok(r):
        return None
    lv = r.json().get('levels') or [[], []]
    if not lv[0]:
        return None
    return {'bids': [[float(l['px']), float(l['sz'])] for l in lv[0]],
            'asks': [[float(l['px']), float(l['sz'])] for l in lv[1]]}


def book_aster(c):
    r = S.get('https://fapi.asterdex.com/fapi/v1/depth',
              params={'symbol': sym('aster', c), 'limit': 500}, timeout=TIMEOUT)
    if not _ok(r):
        return None
    d = r.json()
    if not d.get('bids'):
        return None
    return {'bids': [[float(p), float(q)] for p, q in d['bids']],
            'asks': [[float(p), float(q)] for p, q in d.get('asks', [])]}


def book_lighter(c):
    """★주문 하나하나가 온다. 같은 가격끼리 합쳐야 호가창이 된다."""
    mid = _LIGHTER_MKT.get(sym('lighter', c))
    if mid is None:
        return None
    # ★limit 상한이 있다 — 500 을 넣으면 400 이 온다(실측). 200 이 안전하다.
    r = S.get('https://mainnet.zklighter.elliot.ai/api/v1/orderBookOrders',
              params={'market_id': mid, 'limit': 200}, timeout=TIMEOUT)
    if not _ok(r):
        return None
    d = r.json()

    def agg(rows, reverse):
        acc = {}
        for o in rows or []:
            p = float(o['price'])
            acc[p] = acc.get(p, 0.0) + float(o.get('remaining_base_amount') or 0)
        return [[p, q] for p, q in sorted(acc.items(), reverse=reverse) if q > 0]

    bids, asks = agg(d.get('bids'), True), agg(d.get('asks'), False)
    return {'bids': bids, 'asks': asks} if bids and asks else None


def book_extended(c):
    r = S.get('https://api.starknet.extended.exchange/api/v1/info/markets/%s/orderbook'
              % sym('extended', c), timeout=TIMEOUT)
    if not _ok(r):
        return None
    p = r.json()
    if p.get('status') != 'OK':
        return None
    d = p.get('data') or {}
    if not d.get('bid'):
        return None
    return {'bids': [[float(x['price']), float(x['qty'])] for x in d['bid']],
            'asks': [[float(x['price']), float(x['qty'])] for x in d.get('ask', [])]}


FETCH = {'binance': book_binance, 'bybit': book_bybit, 'okx': book_okx,
         'mexc': book_mexc, 'kucoin': book_kucoin, 'grvt': book_grvt,
         'hyperliquid': book_hyperliquid, 'aster': book_aster,
         'lighter': book_lighter, 'extended': book_extended}


# ══════════════════════════════════════════════════════════════════════════════
# 슬리피지
# ══════════════════════════════════════════════════════════════════════════════
def book_usd(book):
    """책 전체가 담는 달러 — 슬리피지가 좋아 보여도 이게 작으면 못 채운다."""
    if not book:
        return None, None
    b = sum(p * q for p, q in book['bids'])
    a = sum(p * q for p, q in book['asks'])
    return b, a


# ★가격보호밴드 — 거래소는 mid 에서 일정 % 밖 체결을 거부한다(대개 ±5~10%).
#   이걸 안 걸면 깊은 책을 끝까지 쓸어담아 슬리피지가 실제보다 좋게 나온다(GPT 레드팀 지적).
#   밴드에 막힌 것(band_short)과 책이 얕은 것(book_short)을 나눠 적는다 — 원인이 다르다.
PRICE_BAND = 0.10


def slippage(book, usd, side, band=PRICE_BAND):
    """★못 채우면 만들어내지 않는다. None 을 돌려준다.
       얕은 책에서 마지막 호가로 나머지를 채우면 유동성이 있는 것처럼 보인다.

       반환: (bps, 상태, 소비 레벨 수)
       ★소비 레벨 수를 남기는 이유 — 깊이 상한(하이퍼리퀴드 20 등)에 닿았는지 봐야
         책이 얕아서인지 진짜 유동성이 없어서인지 갈린다.
    """
    if not book or not book.get('bids') or not book.get('asks'):
        return None, 'no_book', 0
    bids, asks = book['bids'], book['asks']
    mid = (bids[0][0] + asks[0][0]) / 2
    if mid <= 0:
        return None, 'bad_mid', 0
    levels = asks if side == 'buy' else bids
    lim = mid * (1 + band) if side == 'buy' else mid * (1 - band)
    need, cost, filled, used, hit_band = usd, 0.0, 0.0, 0, False
    for px, qty in levels:
        if px <= 0 or qty <= 0:
            continue
        if (side == 'buy' and px > lim) or (side == 'sell' and px < lim):
            hit_band = True          # ★여기서 멈춘다 — 거래소가 실제로 거부하는 가격이다
            break
        avail = px * qty
        take = min(need, avail)
        cost += take
        filled += take / px
        need -= take
        used += 1
        if need <= 1e-9:
            break
    if need > 1e-9:
        return None, ('band_short' if hit_band else 'book_short'), used
    avg = cost / filled
    bps = (avg / mid - 1) * 1e4 if side == 'buy' else (1 - avg / mid) * 1e4
    return bps, 'ok', used


# ══════════════════════════════════════════════════════════════════════════════
# 실행
# ══════════════════════════════════════════════════════════════════════════════
def fetch_all(coin, venues):
    out = {}
    with ThreadPoolExecutor(max_workers=len(venues)) as ex:
        t0 = time.time()
        fut = {ex.submit(FETCH[v], coin): v for v in venues}
        for f in as_completed(fut):
            v = fut[f]
            try:
                out[v] = f.result()
            except Exception:
                out[v] = None
            out['_t_%s' % v] = round((time.time() - t0) * 1000)
    # 하이퍼리퀴드는 raw 판도 받아 둔다(가격 뭉침의 영향을 보기 위해)
    if 'hyperliquid' in venues:
        try:
            out['hyperliquid_raw'] = book_hyperliquid(coin, nsig=None)
        except Exception:
            out['hyperliquid_raw'] = None
    return out


def run_round(groups=None, venues=None, log=print, sizes=None, pace=PACE_SEC, rnd=0):
    groups = groups or GROUPS
    venues = venues or VENUES
    sizes = sizes or USD_SIZES
    ts = datetime.now().isoformat(timespec='seconds')
    hour = datetime.now().strftime('%Y-%m-%d %H:00')
    rows = []
    first = True
    for gname, coins in groups.items():
        for coin in coins:
            # ★종목 사이에 쉰다. 이게 밴을 막는 유일한 장치다.
            #   429/418 을 받으면 _BACKOFF 가 커져 자동으로 더 쉰다.
            if not first:
                time.sleep(pace * _BACKOFF['mult'])
            first = False
            books = fetch_all(coin, venues)
            live = [v for v in venues if books.get(v)]
            log('  %-5s %-6s 응답 %2d/%d  %s' % (gname, coin, len(live), len(venues),
                                                ' '.join(sorted(set(venues) - set(live))) or ''))
            for v in list(venues) + (['hyperliquid_raw'] if 'hyperliquid' in venues else []):
                bk = books.get(v)
                bu, au = book_usd(bk)
                for usd in sizes:
                    for side in ('buy', 'sell'):
                        bps, note, used = slippage(bk, usd, side)
                        rows.append({
                            'round': rnd, 'ts': ts, 'hour': hour,
                            'group': gname, 'coin': coin,
                            'venue': v, 'symbol': sym(v.replace('_raw', ''), coin)
                            if v.replace('_raw', '') in FETCH else coin,
                            'usd_size': usd, 'side': side,
                            'slippage_bps': bps, 'status': note, 'levels_used': used,
                            # ★extended 는 USD 견적이다. USDT 와 1:1 로 보고 있음을 표시만 해 둔다.
                            'quote_ccy': 'USD' if v.startswith('extended') else 'USDT',
                            # ★거래소마다 응답 시각이 다르다 — 변동장에서 순위가 기울 수 있다
                            'fetched_ms': books.get('_t_%s' % v),
                            'book_usd_bid': round(bu) if bu else None,
                            'book_usd_ask': round(au) if au else None,
                            'fee_bps': FEES.get(v.replace('_raw', ''), None) and
                                       FEES[v.replace('_raw', '')] * 1e4,
                        })
    return rows


def summarize(df, log=print):
    log('\n═══ 요약 — 사이즈별 슬리피지 중위(bps) · 괄호는 못 채운 비율 ═══')
    for g in df['group'].unique():
        d = df[df['group'] == g]
        log('\n[%s]' % g)
        piv = d.pivot_table(index='venue', columns='usd_size', values='slippage_bps',
                            aggfunc='median')
        short = d.assign(bad=(d['status'] == 'book_short')).pivot_table(
            index='venue', columns='usd_size', values='bad', aggfunc='mean')
        for v in piv.index:
            cells = []
            for s in sorted(d['usd_size'].unique()):
                x = piv.loc[v].get(s)
                b = short.loc[v].get(s, 0) if v in short.index else 0
                cells.append('%7s%s' % ('%.1f' % x if pd.notna(x) else '-',
                                        '(%.0f%%)' % (b * 100) if b else '     '))
            log('  %-18s %s' % (v, ' '.join(cells)))


def write_excel(df, path, log=print):
    try:
        with pd.ExcelWriter(path, engine='openpyxl') as w:
            df.to_excel(w, sheet_name='raw', index=False)
            for g in df['group'].unique():
                d = df[(df['group'] == g) & (df['status'] == 'ok')]
                if d.empty:
                    continue
                d.pivot_table(index='venue', columns='usd_size', values='slippage_bps',
                              aggfunc='median').to_excel(w, sheet_name='%s_median' % g)
                d.pivot_table(index=['coin', 'venue'], columns='usd_size',
                              values='slippage_bps', aggfunc='median'
                              ).to_excel(w, sheet_name='%s_by_coin' % g)
            df.pivot_table(index='venue', values=['book_usd_bid', 'book_usd_ask'],
                           aggfunc='median').to_excel(w, sheet_name='book_depth')
        log('-> %s' % path)
    except Exception as e:
        log('★엑셀 저장 실패: %s' % e)


def arg(name, default=None, cast=float):
    """--이름 값 형태로 읽는다."""
    a = sys.argv[1:]
    if name in a:
        i = a.index(name)
        if i + 1 < len(a):
            try:
                return cast(a[i + 1])
            except Exception:
                pass
    return default


def main():
    ap = sys.argv[1:]
    only = [x for x in ap if not x.startswith('-') and x.upper() in GROUPS]
    groups = {k: v for k, v in GROUPS.items() if not only or k in [o.upper() for o in only]}
    sizes = USD_SIZES + (USD_SIZES_EXTRA if '--big' in ap else [])
    interval = arg('--interval', 0, float)      # 라운드 시작 간격(초). 0 이면 1회만
    duration = arg('--duration', 0, float)      # 총 수집 시간(초)
    pace = arg('--pace', PACE_SEC, float)       # 종목 사이 쉬는 시간(초)
    n_coin = sum(len(v) for v in groups.values())

    print('═══ 유동성 벤치마크 ═══')
    print('  거래소 %d (CEX %d · DEX %d) · 종목 %d · 사이즈 %s'
          % (len(VENUES), len(CEX), len(DEX), n_coin,
             ' '.join('%gk' % (s / 1000) for s in sizes)))
    if interval:
        n_round = max(1, int(duration // interval)) if duration else 1
        print('  ★반복: %g초 간격 × %g초 동안 = 약 %d회'
              % (interval, duration, n_round))
    else:
        n_round = 1
        print('  1회만 (반복하려면 --interval 60 --duration 1800)')
    est = n_coin * pace
    print('  ★한 라운드 요청 %d회 · 종목 간 %.1f초 → 약 %.0f초 소요'
          % (n_coin * len(VENUES), pace, est))
    if interval and est > interval:
        print('  ★★간격(%.0f초)이 한 라운드 소요(%.0f초)보다 짧다 — 라운드가 밀린다. '
              '--pace 를 줄이거나 --interval 을 늘려라.' % (interval, est))
    load_contract_sizes()

    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    csv_path = 'liquidity_%s.csv' % stamp
    t_start = time.time()
    all_rows = []
    r = 0
    while True:
        r += 1
        t0 = time.time()
        print('\n── 라운드 %d/%s  %s' % (r, n_round if n_round else '∞',
                                        datetime.now().strftime('%H:%M:%S')))
        rows = run_round(groups, sizes=sizes, pace=pace, rnd=r)
        all_rows += rows
        df_r = pd.DataFrame(rows)
        # ★라운드마다 바로 붙여 쓴다 — 중간에 끊겨도 데이터가 남는다
        df_r.to_csv(csv_path, mode='a', header=(r == 1), index=False, encoding='utf-8-sig')
        ok = (df_r['status'] == 'ok').mean() * 100 if len(df_r) else 0
        print('   %d행 · 성공 %.0f%% · %.0f초 · 막힘 429=%d 418=%d 5xx=%d (지연배수 %.1f)'
              % (len(df_r), ok, time.time() - t0,
                 _RATE['429'], _RATE['418'], _RATE['5xx'], _BACKOFF['mult']))
        if _RATE['418']:
            print('   ★★418 이 왔다 — 밴 직전이다. 즉시 멈추고 간격을 크게 늘려라.')
            break
        if not interval:
            break
        if duration and (time.time() - t_start) >= duration:
            break
        # ★다음 라운드 시작까지 남은 만큼만 쉰다(라운드가 길어져도 간격을 지킨다)
        left = interval - (time.time() - t0)
        if left > 0:
            print('   다음 라운드까지 %.0f초 대기' % left)
            try:
                time.sleep(left)
            except KeyboardInterrupt:
                print('\n★중단 — 지금까지 모은 것은 %s 에 있다' % csv_path)
                break

    df = pd.DataFrame(all_rows)
    print('\n═══ 전체 %d행 · %d라운드 · %.0f분 ═══'
          % (len(df), r, (time.time() - t_start) / 60))
    summarize(df)
    if r > 1:
        # ★시계열이면 라운드 간 흔들림도 봐야 한다 — 한 번 잰 값은 우연일 수 있다
        print('\n═══ 라운드 간 흔들림 (같은 조건의 표준편차 bps) ═══')
        d = df[df['status'] == 'ok']
        if len(d):
            v = d.groupby(['venue', 'usd_size'])['slippage_bps'].std().unstack()
            print(v.round(2).to_string())
    print('\n-> %s' % csv_path)
    write_excel(df, 'liquidity_%s.xlsx' % stamp)


if __name__ == '__main__':
    main()
