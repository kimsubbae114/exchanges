# Perp liquidity benchmark

10개 거래소(CEX 5 · Perp DEX 5)의 **호가창을 실제로 받아** 시장가 주문을 시뮬레이션하고,
주문 규모별 슬리피지를 재서 순위를 매긴다. 매시간 자동으로 돌고, 결과는 웹으로 공개된다.

**보는 곳** → (배포 후 주소가 여기 들어간다)

## 무엇을 재나

| | |
|---|---|
| 거래소 | binance · bybit · okx · mexc · kucoin · **grvt** · hyperliquid · aster · lighter · extended |
| 종목 | 메이저 코인 10종 · 주식/금 perp(RWA) 10종 |
| 주문 규모 | $10k · $50k · $100k · $500k · $1M |
| 지표 | 중위 슬리피지(bps) — 낮을수록 좋다. **수수료는 제외** |

## 어떻게 도나

```
매시간  collect.py   5분 간격 12라운드 수집 → data/recent/YYYYMMDD_HH.csv.gz
        agg.py       최근 24시간을 하나로 집계 → data/agg_latest.json
        history.py   그 시점의 순위를 이력에 append → data/rank_history.json
        build_report.py  리포트 생성 → public/index.html
        (Cloudflare Pages 배포)
```

- **원시는 24시간만 남기고 지운다.** 하루 86MB라 계속 쌓으면 감당이 안 된다.
- **순위 이력은 계속 쌓는다.** 시점당 9KB. 이게 없으면 "어제 몇 등이었나"를 알 수 없다.

## 왜 5분 간격인가

순위 판정은 24시간 안에 **표본 100개 이상**인 칸만 대상으로 한다(`agg.py`의 `MIN_N`).
5분 간격이면 하루 288개라 여유가 있다. 15분 간격이면 96개로 미달이다.

## 화면이 지키는 것 — 착시를 막는 장치

이 리포트는 GRVT 소속이 만든다. 자기편에 유리하게 기우는 걸 **구조로** 막아야 했다.

| 착시 | 막는 방법 |
|---|---|
| 커버리지 | MEXC는 RWA 10종 중 2종만 상장. 없는 종목이 평균에서 빠지면 1위가 된다 → **공통 상장 종목만** 비교하는 판을 따로 둔다 |
| 미체결 | 그 규모를 못 사는 곳이 최고로 보인다 → 못 채운 칸은 **빗금 + 순위 제외** |
| 한 번 재기 | aster·kucoin은 라운드마다 30~80bps 출렁인다 → 중위만이 아니라 p10~p90과 σ |
| 표본 부족 | 표본 100 미만·체결률 95% 미만은 **순위에서 뺀다** |
| 강조 편향 | GRVT에 강조색을 주지 않는다. 추이 차트는 **어느 거래소든 골라** 강조할 수 있다 |
| 순위의 상대성 | 7등→3등이 우리가 좋아진 것인지 남이 나빠진 것인지 모른다 → **순위와 슬리피지를 나란히** 그린다 |

결과가 GRVT에 불리해도 그대로 싣는다. 실제로 메이저 공통 10종목 기준 10곳 중 7~8위다.

## 직접 돌려보기

```bash
pip install -r requirements.txt
python collect.py --rounds 2 --gap 60    # 짧게 시험
python agg.py && python history.py && python build_report.py
# public/index.html 을 브라우저로 연다
```

## 배포 설정

Cloudflare Pages로 배포하려면 저장소 **Settings → Secrets and variables → Actions** 에
아래 둘을 넣는다. 없으면 배포 단계만 건너뛰고 수집은 계속 쌓인다.

| 이름 | 값 |
|---|---|
| `CLOUDFLARE_API_TOKEN` | Cloudflare → My Profile → API Tokens 에서 발급 (Pages 편집 권한) |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 대시보드 우측에 있는 Account ID |

## 지키는 선

공개 REST 엔드포인트만 쓴다. 로그인·인증·주문은 하지 않는다.
종목 사이에 간격을 두고, 429/418을 받으면 자동으로 더 쉰다.
