# -*- coding: utf-8 -*-
"""
NH_Farm_Stock 일일 데이터 갱신 (실제 API 연동판)

흐름:
1. data.go.kr 'katOrigin/trades' API로 5개 시장 x 38개 품목의
   실제 반입량(qty)과 경락 단가(scsbd_prc)를 조회 (조회일=어제, KST)
2. 조회 성공한 품목 -> 실데이터로 prices/vol 교체, chg는 (신규-기존)/기존*100 로 계산
3. 조회 실패/데이터 없음 품목 -> 기존 방식(소폭 랜덤 변동)으로 보완
4. API 키 미설정 시 전체 랜덤 변동 (기존 동작과 동일, 안전장치)
"""
import os
import re
import time
import random
import shutil
from datetime import datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
today = now.strftime("%Y-%m-%d")
yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
random.seed(f"{today}-{'AM' if now.hour < 10 else 'PM'}")

KEY = os.environ.get("AT_API_KEY", "")
BASE = "https://apis.data.go.kr/B552845/katOrigin"
MKTS_K = ["garak", "daejeon", "busan", "gwangju", "daegu"]

MARKETS = {
    "garak": "110001", "daejeon": "250001", "busan": "210001",
    "gwangju": "240001", "daegu": "220001",
}

# 품목명 -> (대분류, 중분류, [소분류코드...] or None=중분류 전체)
ITEM_CODES = {
    "수미감자":   ("05", "01", ["01"]),
    "두백감자":   ("05", "01", ["13"]),
    "홍감자":     ("05", "01", ["18"]),
    "후지사과":   ("06", "01", ["03"]),
    "홍로사과":   ("06", "01", ["17"]),
    "감홍사과":   ("06", "01", ["29"]),
    "배":         ("06", "02", ["01"]),
    "거봉포도":   ("06", "03", ["02"]),
    "캠벨포도":   ("06", "03", ["01"]),
    "샤인머스켓": ("06", "03", ["36"]),
    "백도복숭아": ("06", "04", ["11", "55", "F4", "83", "62", "98"]),
    "황도복숭아": ("06", "04", ["92"]),
    "천도복숭아": ("06", "04", ["47", "E7", "E8", "B4"]),
    "단감":       ("06", "05", ["01"]),
    "태추단감":   ("06", "05", ["22"]),
    "감귤":       ("06", "14", None),
    "수박":       ("08", "01", ["00"]),
    "일반토마토": ("08", "03", ["03"]),
    "딸기":       ("08", "04", ["00"]),
    "방울토마토": ("08", "06", ["01"]),
    "백오이":     ("09", "01", ["02"]),
    "취청오이":   ("09", "01", ["01"]),
    "가시오이":   ("09", "01", ["03"]),
    "애호박":     ("09", "02", ["01"]),
    "쥬키니":     ("09", "02", ["02"]),
    "단호박":     ("09", "02", ["05"]),
    "배추":       ("10", "01", ["00"]),
    "양배추":     ("10", "04", ["01"]),
    "적상추":     ("10", "05", ["02"]),
    "청상추":     ("10", "05", ["01"]),
    "포기상추":   ("10", "05", ["03", "04"]),
    "무":         ("11", "01", ["00"]),
    "양파":       ("12", "01", ["01"]),
    "대파":       ("12", "02", ["01"]),
    "풋고추":     ("12", "05", ["05"]),
    "청양고추":   ("12", "05", ["01"]),
}

GROUPS = {}
for nm, (l, mc, _) in ITEM_CODES.items():
    GROUPS.setdefault((l, mc), []).append(nm)


def fetch_trades(whsl_mrkt_cd, lclsf, mclsf, ymd, retries=2):
    params = {
        "serviceKey": KEY, "returnType": "json", "numOfRows": 1000, "pageNo": 1,
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[gds_lclsf_cd::EQ]": lclsf,
        "cond[gds_mclsf_cd::EQ]": mclsf,
        "cond[trd_clcln_ymd::EQ]": ymd,
        "selectable": "gds_sclsf_cd,unit_qty,unit_nm,qty,scsbd_prc",
    }
    for attempt in range(retries + 1):
        try:
            r = requests.get(f"{BASE}/trades", params=params, timeout=25)
            data = r.json()
            items = data.get("response", {}).get("body", {}).get("items", {})
            if not items:
                return []
            arr = items.get("item", [])
            return [arr] if isinstance(arr, dict) else arr
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            print(f"  ⚠️ fetch 실패 ({whsl_mrkt_cd},{lclsf}-{mclsf}): {e}")
            return None


def aggregate(items, sclsf_filter):
    """반입량(kg합계)과 가중평균 단가(원/kg)를 계산. 데이터 없으면 None."""
    valid = []
    for it in items:
        if sclsf_filter is not None and it.get("gds_sclsf_cd", "") not in sclsf_filter:
            continue
        try:
            qty = float(it.get("qty", 0) or 0)
            price = float(it.get("scsbd_prc", 0) or 0)
            unit_qty = float(it.get("unit_qty", 0) or 0)
        except (TypeError, ValueError):
            continue
        if qty <= 0 or price <= 0:
            continue
        valid.append((qty, price, unit_qty if unit_qty > 0 else 1.0))
    if not valid:
        return None
    total_qty_kg = sum(q * u for q, _, u in valid)
    total_amount = sum(q * p for q, p, _ in valid)
    total_qty = sum(q for q, _, _ in valid)
    return {"qty_kg": total_qty_kg, "avg_price_per_unit": total_amount / total_qty}


# ──────────────────────────────────────────
# 1) API에서 실데이터 수집
# ──────────────────────────────────────────
results = {}
if KEY:
    api_ok = api_fail = 0
    for (lclsf, mc), names in GROUPS.items():
        for mkey, mcode in MARKETS.items():
            items = fetch_trades(mcode, lclsf, mc, yesterday)
            if items is None:
                api_fail += 1
                continue
            api_ok += 1
            for nm in names:
                _, _, sclsf_filter = ITEM_CODES[nm]
                agg = aggregate(items, sclsf_filter)
                if agg:
                    results.setdefault(nm, {})[mkey] = agg
            time.sleep(0.1)
    print(f"▶ API 호출: 성공 {api_ok} / 실패 {api_fail}  |  데이터 확보 품목: {len(results)}/{len(ITEM_CODES)}")
else:
    print("⚠️ AT_API_KEY 미설정 — 전체 랜덤 변동 모드")

# ──────────────────────────────────────────
# 2) index.html 로드 + 단위 정보 추출
# ──────────────────────────────────────────
with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

box_kg_m = re.search(r"const BOX_KG=\{(.*?)\};", html, re.S)
BOX_KG = {k: float(v) for k, v in re.findall(r"'([^']+)':([\d.]+)", box_kg_m.group(1))} if box_kg_m else {}

piece_m = re.search(r"const PIECE_ITEMS=\{(.*?)\};", html, re.S)
PIECE_ITEMS = {k: int(v) for k, v in re.findall(r"'([^']+)':(\d+)", piece_m.group(1))} if piece_m else {}

ITEM_BLOCK = re.compile(
    r"(\{name:'([^']+)',(?:(?!prices:\{|\{name:').)*?prices:\{)garak:(\d+),daejeon:(\d+),busan:(\d+),gwangju:(\d+),daegu:(\d+)"
    r"(\},\s*chg:\{)garak:([-\d.]+),daejeon:([-\d.]+),busan:([-\d.]+),gwangju:([-\d.]+),daegu:([-\d.]+)"
    r"(\},\s*vol:\{)garak:(\d+(?:\.\d+)?),daejeon:(\d+(?:\.\d+)?),busan:(\d+(?:\.\d+)?),gwangju:(\d+(?:\.\d+)?),daegu:(\d+(?:\.\d+)?)(\})",
    re.S,
)


def process(m):
    name = m.group(2)
    old_prices = [int(m.group(i)) for i in (3, 4, 5, 6, 7)]
    old_vols = [float(m.group(i)) for i in (15, 16, 17, 18, 19)]

    market_data = results.get(name)
    if market_data:
        div = PIECE_ITEMS.get(name) or BOX_KG.get(name, 10)
        if name == "수박":
            div = 2  # 18kg(2입) 박스 -> 1통(9kg) 가격
        new_prices, new_vols, new_chgs = [], [], []
        for i, mkey in enumerate(MKTS_K):
            agg = market_data.get(mkey)
            if agg:
                new_price = max(100, round(agg["avg_price_per_unit"] * div))
                new_vol = round(agg["qty_kg"] / 1000, 1)  # kg -> 톤
            else:
                new_price = old_prices[i]
                new_vol = old_vols[i]
            chg = round((new_price - old_prices[i]) / old_prices[i] * 100, 1) if old_prices[i] > 0 else 0.0
            new_prices.append(new_price)
            new_vols.append(new_vol)
            new_chgs.append(chg)
    else:
        # 실데이터 없음 -> 기존 방식(소폭 랜덤 변동)
        base = random.gauss(0, 2.2)
        if random.random() < 0.08:
            base = random.choice([-1, 1]) * random.uniform(7, 15)
        new_prices, new_vols, new_chgs = [], [], []
        for i in range(5):
            chg = max(-18.0, min(22.0, base + random.gauss(0, 0.6)))
            price = max(100, round(old_prices[i] * (1 + chg / 100) / 10) * 10)
            vol = max(0.1, round(old_vols[i] * random.uniform(0.94, 1.06), 1))
            new_prices.append(price)
            new_vols.append(vol)
            new_chgs.append(round(chg, 1))

    p = ",".join(f"{k}:{v}" for k, v in zip(MKTS_K, new_prices))
    c = ",".join(f"{k}:{v}" for k, v in zip(MKTS_K, new_chgs))
    v = ",".join(f"{k}:{v}" for k, v in zip(MKTS_K, new_vols))

    return (
        m.group(1) + p
        + m.group(8) + c
        + m.group(14) + v
        + m.group(20)
    )


count = 0
real_count = 0
def repl(m):
    global count, real_count
    count += 1
    if m.group(2) in results and results[m.group(2)]:
        real_count += 1
    return process(m)

html = ITEM_BLOCK.sub(repl, html)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

os.makedirs("archive", exist_ok=True)
shutil.copy("index.html", f"archive/{yesterday}.html")

print(f"✅ {now.strftime('%Y-%m-%d %H:%M')} KST — {count}개 품목 처리 (실데이터 반영 {real_count}개)")
if count == 0:
    raise SystemExit("⚠️ 처리된 품목이 0개 — index.html 구조 확인 필요")
