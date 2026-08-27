# -*- coding: utf-8 -*-
"""한 시간 치를 수집한다 — GitHub Actions 가 매시간 이걸 부른다.

왜 이렇게 나눴나
 · 리포트는 표본이 100 라운드 미만인 칸을 **순위에서 뺀다**(agg.py 의 MIN_N).
   24시간 안에 그걸 채우려면 **5분 간격**이어야 한다(하루 288라운드).
 · 그런데 GitHub Actions 의 cron 은 5분 간격을 약속하지 않는다 — 부하가 몰리면
   수십 분씩 밀리고 아예 건너뛰기도 한다. 그래서 **매시간 한 번 깨어나
   그 안에서 5분 간격으로 12라운드**를 돈다. 밀림에 영향을 받지 않는다.

저장
 · data/recent/YYYYMMDD_HH.csv.gz — 원시. **24시간 지난 것은 지운다.**
   원시를 계속 쌓으면 하루 86MB 다. 24시간 리포트에 필요한 만큼만 남긴다.
 · 과거는 agg 단계에서 **일별 요약**으로 축약해 남긴다(하루 0.3MB).

★공개 저장소에 올라간다. 여기 있는 것은 전부 공개 API 로 얻은 호가뿐이고
  키·계정·개인정보는 들어가지 않는다.
"""
import argparse
import datetime as dt
import pathlib
import sys
import time

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = pathlib.Path(__file__).resolve().parent
RECENT = ROOT / 'data' / 'recent'
KEEP_HOURS = 24                  # 이만큼만 원시를 남긴다
DEFAULT_ROUNDS = 12              # 매시간 12라운드
DEFAULT_GAP = 300                # 5분 간격


def sweep_old():
    """24시간 넘은 원시 파일을 지운다. 안 지우면 저장소가 계속 불어난다."""
    cut = dt.datetime.now() - dt.timedelta(hours=KEEP_HOURS)
    gone = 0
    for f in RECENT.glob('*.csv.gz'):
        try:
            stamp = dt.datetime.strptime(f.name[:11], '%Y%m%d_%H')
        except ValueError:
            continue
        if stamp < cut:
            f.unlink(); gone += 1
    if gone:
        print('   오래된 원시 %d개 지움 (%d시간 초과)' % (gone, KEEP_HOURS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rounds', type=int, default=DEFAULT_ROUNDS)
    ap.add_argument('--gap', type=int, default=DEFAULT_GAP, help='라운드 간격(초)')
    ap.add_argument('--budget', type=int, default=55 * 60,
                    help='이 시간을 넘기면 남은 라운드를 포기한다(초)')
    a = ap.parse_args()

    import benchmark_major_rwa as B          # 수집 본체는 손대지 않고 그대로 쓴다

    # ★반드시 먼저 불러야 한다. main() 을 거치지 않고 run_round() 를 직접 부르므로
    #   이걸 빠뜨리면 초기화가 통째로 건너뛰어진다. 실제로 그래서
    #     · lighter 가 market_id 를 몰라 전 종목 no_book 이 되고
    #     · mexc 계약크기가 기본값 1.0 이 되어 슬리피지가 어긋났다.
    B.load_contract_sizes(log=lambda *x: None)
    B.load_fees(log=print)          # 공개 API 로 받을 수 있는 수수료는 받아 온다

    RECENT.mkdir(parents=True, exist_ok=True)
    out = RECENT / (dt.datetime.now().strftime('%Y%m%d_%H') + '.csv.gz')
    print('★수집 시작 — %d라운드 · %d초 간격 · 예산 %d분' % (a.rounds, a.gap, a.budget // 60))
    t0 = time.time()
    frames = []
    for r in range(1, a.rounds + 1):
        left = a.budget - (time.time() - t0)
        if left < 60:
            print('   예산이 %.0f초 남아 %d라운드에서 멈춘다' % (left, r - 1)); break
        rs = time.time()
        try:
            rows = B.run_round(rnd=r, log=lambda *x: None)
        except Exception as e:
            print('   ★라운드 %d 실패: %s: %s' % (r, type(e).__name__, e)); continue
        df = pd.DataFrame(rows)
        frames.append(df)
        ok = int((df.status == 'ok').sum()) if 'status' in df else 0
        print('   %2d/%d · %d행 · 체결 %d · %.0f초'
              % (r, a.rounds, len(df), ok, time.time() - rs))
        if r < a.rounds:
            wait = a.gap - (time.time() - rs)
            if wait > 0:
                time.sleep(wait)

    if not frames:
        print('★한 라운드도 못 모았다. 파일을 쓰지 않는다.'); sys.exit(1)
    d = pd.concat(frames, ignore_index=True)
    # ★같은 시간대에 두 번 돌면 이어 붙인다(재실행·수동 실행 대비)
    if out.exists():
        old = pd.read_csv(out, low_memory=False)
        d['round'] = d['round'] + int(old['round'].max())
        d = pd.concat([old, d], ignore_index=True)
    d.to_csv(out, index=False, compression='gzip')
    print('\n★저장 %s · %s행 · %.2f MB'
          % (out.name, '{:,}'.format(len(d)), out.stat().st_size / 1e6))
    sweep_old()
    files = sorted(RECENT.glob('*.csv.gz'))
    tot = sum(f.stat().st_size for f in files) / 1e6
    print('   최근 %d시간 보관: 파일 %d개 · %.1f MB' % (KEEP_HOURS, len(files), tot))


if __name__ == '__main__':
    main()
