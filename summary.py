# -*- coding: utf-8 -*-
"""실행 요약 — GitHub Actions 화면에 뭐가 됐는지 한눈에 남긴다.

★워크플로 안에 파이썬을 heredoc 으로 끼워 넣지 않고 파일로 뺐다.
  yml 안의 heredoc 은 들여쓰기·따옴표가 얽혀 조용히 깨지기 쉽고,
  깨져도 "요약 실패"로만 보여 원인을 못 찾는다. 파일이면 여기서 시험할 수 있다.
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = pathlib.Path(__file__).resolve().parent

recent = sorted((ROOT / 'data' / 'recent').glob('*.csv.gz'))
mb = sum(f.stat().st_size for f in recent) / 1e6
print('- 원시 %d시간치 · %.1f MB' % (len(recent), mb))

hp = ROOT / 'data' / 'rank_history.json'
if not hp.exists():
    print('- 순위 이력 없음')
    sys.exit(0)

h = json.loads(hp.read_text(encoding='utf-8'))
stamps = sorted({x['at'] for x in h})
print('- 순위 이력 %d줄 · 시점 %d개 (%s ~ %s)'
      % (len(h), len(stamps), stamps[0][5:16], stamps[-1][5:16]))

cur = [x for x in h if x['at'] == stamps[-1] and x['group'] == 'MAJOR']
for r in sorted(cur, key=lambda y: y['size'])[:2]:
    order = sorted([(d['rank'], v) for v, d in r['ranks'].items() if d.get('rank')])
    if not order:
        print('- $%s: 순위 없음 (표본 부족)' % '{:,}'.format(r['size']))
        continue
    print('- $%s: %s' % ('{:,}'.format(r['size']),
                         ' · '.join('%d.%s' % (n, v) for n, v in order)))
    me = r['ranks'].get('grvt') or {}
    if me.get('rank'):
        print('  - **grvt %d위** · 중위 %.2f bps · 표본 %s'
              % (me['rank'], me['med'], '{:,}'.format(me.get('n', 0))))
