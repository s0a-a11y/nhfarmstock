# -*- coding: utf-8 -*-
"""
NH_Farm_Stock 일일 데이터 갱신
- index.html 내 21개 품목의 경락가/등락률/반입량을 매 실행마다 갱신
- 날짜·히어로 카드는 사이트 JS가 자동 처리하므로 데이터만 갱신
- 같은 날 6시/12시 실행 시 12시는 소폭 추가 변동만 반영 (날짜 시드)
"""
import os
import re
import random
import shutil
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
today = now.strftime("%Y-%m-%d")
yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

# 날짜+오전/오후 시드 → 같은 실행시간대엔 동일 결과 (재실행 안전)
random.seed(f"{today}-{'AM' if now.hour < 10 else 'PM'}")

with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

MKTS = ["garak", "daejeon", "busan", "gwangju", "daegu"]

PATTERN = re.compile(
    r"prices:\{garak:(\d+),daejeon:(\d+),busan:(\d+),gwangju:(\d+),daegu:(\d+)\},\s*"
    r"chg:\{garak:([-\d.]+),daejeon:([-\d.]+),busan:([-\d.]+),gwangju:([-\d.]+),daegu:([-\d.]+)\},\s*"
    r"vol:\{garak:(\d+),daejeon:(\d+),busan:(\d+),gwangju:(\d+),daegu:(\d+)\}"
)

count = 0

def mutate(m):
    global count
    count += 1
    old_prices = [int(m.group(i)) for i in range(1, 6)]
    old_vols = [int(m.group(i)) for i in range(11, 16)]

    # 품목 공통 추세 + 시장별 편차 (대부분 ±3%, 가끔 급등락)
    base = random.gauss(0, 2.2)
    if random.random() < 0.08:                      # 8% 확률 급변동
        base = random.choice([-1, 1]) * random.uniform(7, 15)

    new_prices, new_chgs, new_vols = [], [], []
    for i in range(5):
        chg = max(-18.0, min(22.0, base + random.gauss(0, 0.6)))
        price = max(500, round(old_prices[i] * (1 + chg / 100) / 10) * 10)
        vol = max(3, round(old_vols[i] * random.uniform(0.94, 1.06)))
        new_prices.append(price)
        new_chgs.append(round(chg, 1))
        new_vols.append(vol)

    p = ",".join(f"{k}:{v}" for k, v in zip(MKTS, new_prices))
    c = ",".join(f"{k}:{v}" for k, v in zip(MKTS, new_chgs))
    v = ",".join(f"{k}:{v}" for k, v in zip(MKTS, new_vols))
    return f"prices:{{{p}}},\n   chg:{{{c}}},\n   vol:{{{v}}}"

html = PATTERN.sub(mutate, html)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

# 어제자 보관
os.makedirs("archive", exist_ok=True)
shutil.copy("index.html", f"archive/{yesterday}.html")

print(f"✅ {now.strftime('%Y-%m-%d %H:%M')} KST — {count}개 품목 시세 갱신 완료")
if count == 0:
    raise SystemExit("⚠️ 갱신된 품목이 0개 — index.html 구조를 확인하세요!")
