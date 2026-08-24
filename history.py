# -*- coding: utf-8 -*-
"""순위 이력을 쌓는다 — "오늘은 7등인데 어제는 3등이었다"를 보여주기 위한 것.

원시는 24시간만 남기고 지운다. 그래서 **과거를 보려면 이 파일이 있어야 한다.**
집계 한 번에 한 줄씩 쌓이고, 하루 24줄이면 1년에 8,760줄 — 아주 작다.

★GRVT 만 기록하지 않는다. 순위는 상대적이라, 남이 좋아져서 내가 밀린 것과
  내가 나빠져서 밀린 것은 전혀 다른 이야기다. 그걸 구분하려면 전부 있어야 한다.
  그래서 거래소별 **순위와 중위 슬리피지를 같이** 남긴다.

산출: data/rank_history.json
   [{at, group, size, ranks:{venue:{rank, med, n, rankable}}, of}, …]
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = pathlib.Path(__file__).resolve().parent
AGG = ROOT / 'data' / 'agg_latest.json'
HIST = ROOT / 'data' / 'rank_history.json'
KEEP = 24 * 90          # 90일치까지 (시간당 1줄)
SCOPE = 'common'        # ★공통 상장 종목 기준. 커버리지 착시를 피하려면 이쪽이어야 한다.


def main():
    if not AGG.exists():
        print('★%s 가 없다. agg.py 를 먼저 돌려야 한다.' % AGG); sys.exit(1)
    a = json.loads(AGG.read_text(encoding='utf-8'))
    # ★시점은 **데이터의 마지막 관측 시각**이다. 빌드한 시각이 아니다.
    #   빌드 시각을 쓰면 "언제의 유동성인가"가 아니라 "언제 그렸나"가 되어,
    #   몰아서 다시 그리면 시점이 전부 같은 값으로 뭉개진다(실제로 그렇게 나왔다).
    at = a['meta']['span'][1] or a['meta'].get('built_at')
    venues = a['meta']['venues']
    sizes = a['meta']['sizes']

    hist = json.loads(HIST.read_text(encoding='utf-8')) if HIST.exists() else []
    added = 0
    for g in ('MAJOR', 'RWA'):
        t = a['scope'][g][SCOPE]['table']
        for s in sizes:
            # 순위 자격이 있는 칸만 줄 세운다 — 표본이 적거나 자주 못 채운 곳은 뺀다
            vals = [(v, t[v][str(s)]['med']) for v in venues
                    if t.get(v, {}).get(str(s)) and t[v][str(s)].get('rankable')
                    and t[v][str(s)].get('med') is not None]
            vals.sort(key=lambda x: x[1])
            rank = {v: i for i, (v, _) in enumerate(vals, 1)}
            row = {'at': at, 'group': g, 'size': s, 'of': len(vals), 'ranks': {}}
            for v in venues:
                c = t.get(v, {}).get(str(s)) or {}
                row['ranks'][v] = {
                    'rank': rank.get(v),                 # 자격 없으면 None
                    'med': c.get('med'), 'n': c.get('n'),
                    'fill': c.get('fill'), 'rankable': c.get('rankable', False)}
            # 같은 시각·같은 칸이 이미 있으면 덮어쓴다(재실행 대비)
            hist = [h for h in hist
                    if not (h['at'] == at and h['group'] == g and h['size'] == s)]
            hist.append(row); added += 1

    # ★순위가 하나도 안 나온 시점은 남기지 않는다.
    #   표본이 아직 적어(MIN_N 미달) 아무도 줄 세울 수 없는 상태인데,
    #   그걸 이력에 남기면 추이 선이 이유 없이 끊어져 보인다.
    #   "데이터가 없는 것"과 "순위를 매길 수 없는 것"은 다르다.
    empty = {a for a in {h['at'] for h in hist}
             if not any(d.get('rank') for h in hist if h['at'] == a
                        for d in h['ranks'].values())}
    if empty:
        hist = [h for h in hist if h['at'] not in empty]
        print('   ★순위가 없는 시점 %d개는 기록하지 않았다 (표본 부족) — %s'
              % (len(empty), ' · '.join(sorted(empty))))

    hist.sort(key=lambda h: (h['at'], h['group'], h['size']))
    # 오래된 것 정리 — 시각 기준으로 최근 것부터 남긴다
    stamps = sorted({h['at'] for h in hist})
    if len(stamps) > KEEP:
        keep = set(stamps[-KEEP:])
        hist = [h for h in hist if h['at'] in keep]
    HIST.write_text(json.dumps(hist, ensure_ascii=False), encoding='utf-8')

    print('★순위 이력 %d줄 추가 · 총 %d줄 · 시점 %d개 · %.0f KB'
          % (added, len(hist), len(stamps), HIST.stat().st_size / 1e3))
    # 지금 순위를 한 번 보여 준다 — 무엇이 기록됐는지 눈으로 확인하려고
    for g in ('MAJOR', 'RWA'):
        cur = [h for h in hist if h['group'] == g and h['at'] == stamps[-1]]
        for h in sorted(cur, key=lambda x: x['size'])[:2]:
            order = sorted([(d['rank'], v) for v, d in h['ranks'].items() if d['rank']])
            print('   %-5s $%-9s %s' % (g, '{:,}'.format(h['size']),
                                        ' · '.join('%d.%s' % (r, v) for r, v in order)))


if __name__ == '__main__':
    main()
