# -*- coding: utf-8 -*-
"""
시장간 격차(gap%)가 비정상적으로 큰 품목들의 raw 데이터(unit_qty/scsbd_prc/pkg_nm)를
시장별로 출력. 특히 daegu(북부도매시장)에서 price_per_kg이 유독 낮게 나오는
패턴(대파, 청양고추)과 garak에서 유독 높게 나오는 패턴(감귤하우스, 청상추)을 검증.
"""
import os
import time
import requests
from collections import Counter
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

KEY = os.environ["AT_API_KEY"]
BASE = "https://apis.data.go.kr/B552845/katOrigin"

MARKETS = {
    "garak": "110001", "daejeon": "250001", "busan": "210001",
    "gwangju": "240001", "daegu": "220001",
}

# (이름, 대분류, 중분류, 소분류필터)
TARGETS = [
    ("대파", "12", "02", ["01"]),
    ("청양고추", "12", "05", ["01"]),
    ("후지사과", "06", "01", ["03"]),
    ("감귤(하우스)", "06", "14", ["05"]),
    ("청상추", "10", "05", ["01"]),
    ("적상추", "10", "05", ["02"]),
]


def fetch(whsl_mrkt_cd, lclsf, mclsf, ymd):
    params = {
        "serviceKey": KEY, "returnType": "json", "numOfRows": 1000, "pageNo": 1,
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[gds_lclsf_cd::EQ]": lclsf,
        "cond[gds_mclsf_cd::EQ]": mclsf,
        "cond[trd_clcln_ymd::EQ]": ymd,
        "selectable": "gds_sclsf_cd,gds_sclsf_nm,unit_qty,unit_nm,qty,scsbd_prc,totprc,pkg_nm",
    }
    r = requests.get(f"{BASE}/trades", params=params, timeout=25)
    data = r.json()
    items = data.get("response", {}).get("body", {}).get("items", {})
    if not items:
        return []
    arr = items.get("item", [])
    return [arr] if isinstance(arr, dict) else arr


for name, lclsf, mclsf, sclsf_filter in TARGETS:
    print(f"\n{'='*70}")
    print(f"▶ {name} (lclsf={lclsf}, mclsf={mclsf}, sclsf_filter={sclsf_filter})")
    print(f"{'='*70}")
    for mkey, mcode in MARKETS.items():
        items = fetch(mcode, lclsf, mclsf, yesterday)
        filtered = [it for it in items if sclsf_filter is None or it.get("gds_sclsf_cd","") in sclsf_filter]
        print(f"\n  [{mkey}] 전체={len(items)}, 필터후={len(filtered)}")
        if not filtered:
            time.sleep(0.1)
            continue

        # unit_qty별로 그룹화하여 각 그룹의 price_per_kg 계산
        by_unit = {}
        for it in filtered:
            try:
                qty = float(it.get("qty",0) or 0)
                price = float(it.get("scsbd_prc",0) or 0)
                unit_qty = float(it.get("unit_qty",0) or 0)
            except (TypeError, ValueError):
                continue
            if qty<=0 or price<=0 or unit_qty<=0:
                continue
            by_unit.setdefault(unit_qty, []).append((qty, price))

        for u, lst in sorted(by_unit.items()):
            total_qty = sum(q for q,_ in lst)
            total_amt = sum(q*p for q,p in lst)
            total_kg = sum(q*u for q,_ in lst)
            avg_price_per_pkg = total_amt/total_qty
            price_per_kg = total_amt/total_kg
            pkg_nms = Counter(it.get("pkg_nm") for it in filtered if float(it.get("unit_qty",0) or 0)==u)
            print(f"    unit_qty={u:5.1f}kg | 건수={len(lst):3d} | sum(qty)={total_qty:8.1f} | "
                  f"avg_price/pkg={avg_price_per_pkg:10.1f} | price_per_kg={price_per_kg:8.1f} | "
                  f"pkg_nm={dict(pkg_nms)}")
        time.sleep(0.1)
