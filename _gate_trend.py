# -*- coding: utf-8 -*-
"""추이 화면 게이트 — **실제 파이프라인을 여러 번 돌려** 시점을 쌓고 확인한다.

가짜 데이터를 만들어 넣지 않는다. 원시 파일을 한 시간씩 늘려 가며
agg → history 를 실제로 실행한다. 운영에서 매시간 일어나는 일과 같은 경로다.

끝나면 원래 상태(전체 파일)로 되돌린다.
"""
import json
import pathlib
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = pathlib.Path(__file__).resolve().parent
RECENT = ROOT / 'data' / 'recent'
HOLD = ROOT / 'data' / '_hold'
HIST = ROOT / 'data' / 'rank_history.json'


def run(script):
    r = subprocess.run([sys.executable, script], cwd=str(ROOT), capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print('   ★%s 실패:' % script)
        print((r.stderr or '')[-400:])
    return r.returncode == 0


files = sorted(RECENT.glob('*.csv.gz'))
if len(files) < 2:
    print('★원시가 %d개뿐이라 추이를 만들 수 없다.' % len(files)); sys.exit(1)

print('원시 %d개로 시점 %d개를 만든다 (한 개씩 늘려 가며)' % (len(files), len(files)))
HOLD.mkdir(exist_ok=True)
for f in files:
    shutil.move(str(f), str(HOLD / f.name))
if HIST.exists():
    HIST.unlink()

try:
    for i, f in enumerate(sorted(HOLD.glob('*.csv.gz')), 1):
        shutil.copy2(str(f), str(RECENT / f.name))
        ok = run('agg.py') and run('history.py')
        print('   %d/%d  %s  %s' % (i, len(files), f.name, 'OK' if ok else '★실패'))
finally:
    for f in RECENT.glob('*.csv.gz'):
        f.unlink()
    for f in HOLD.glob('*.csv.gz'):
        shutil.move(str(f), str(RECENT / f.name))
    HOLD.rmdir()

h = json.loads(HIST.read_text(encoding='utf-8'))
stamps = sorted({x['at'] for x in h})
print('\n★순위 이력 %d줄 · 시점 %d개' % (len(h), len(stamps)))
print('   시점: %s' % ' · '.join(s[11:16] for s in stamps))

# GRVT 순위가 실제로 움직였는지 — 움직임이 없으면 화면에서 확인할 게 없다
for g in ('MAJOR',):
    for size in sorted({x['size'] for x in h})[:2]:
        seq = [(x['at'][11:16], (x['ranks'].get('grvt') or {}).get('rank'))
               for x in sorted(h, key=lambda y: y['at'])
               if x['group'] == g and x['size'] == size]
        print('   %-5s $%-9s grvt 순위: %s'
              % (g, '{:,}'.format(size), ' → '.join(str(r) for _, r in seq)))
run('build_report.py')
print('\n-> public/index.html 다시 만들었다')
