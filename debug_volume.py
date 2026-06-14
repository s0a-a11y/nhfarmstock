# -*- coding: utf-8 -*-
"""
물량(qty)/단위물량(unit_qty)/단위총물량(unit_tot_qty)/낙찰가(scsbd_prc)/총가격(totprc)
관계를 raw 데이터로 검증하기 위한 디버그 스크립트.

확인 대상:
- 양파(가락 vol=0.9톤, 대구 vol=246.2톤 — 극단적 불균형)
- 백오이(가락 vol=274.6톤 — 압도적 1위)
- 일반 비교군: 배추(상대적으로 균형)
"""
import os
import json
import requests
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

# 검증 대상: (이름, 대분류, 중분류, 소분류필터)
TARGETS = [
    ("양파", "12", "01", ["01"]),
    ("백오이", "09", "01", ["02"]),
    ("배추", "10", "01", ["00"]),
]


def fetch(whsl_mrkt_cd, lclsf, mclsf, ymd):
    params = {
        "serviceKey": KEY, "returnType": "json", "numOfRows": 1000, "pageNo": 1,
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[gds_lclsf_cd::EQ]": lclsf,
        "cond[gds_mclsf_cd::EQ]": mclsf,
        "cond[trd_clcln_ymd::EQ]": ymd,
        "selectable": "gds_sclsf_cd,unit_qty,unit_nm,unit_cd,qty,scsbd_prc,unit_tot_qty,totprc,pkg_nm",
    }
    r = requests.get(f"{BASE}/trades", params=params, timeout=25)
    data = r.json()
    items = data.get("response", {}).get("body", {}).get("items", {})
    if not items:
        return []
    arr = items.get("item", [])
    return [arr] if isinstance(arr, dict) else arr


for name, lclsf, mclsf, sclsf_filter in TARGETS:
    print(f"\n{'='*60}")
    print(f"▶ {name} (lclsf={lclsf}, mclsf={mclsf}, sclsf_filter={sclsf_filter})")
    print(f"{'='*60}")
    for mkey, mcode in MARKETS.items():
        items = fetch(mcode, lclsf, mclsf, yesterday)
        filtered = [it for it in items if sclsf_filter is None or it.get("gds_sclsf_cd","") in sclsf_filter]
        print(f"\n  [{mkey}] 전체 거래건수={len(items)}, 필터후={len(filtered)}")
        if not filtered:
            continue

        # 합계 비교
        sum_qty = sum(float(it.get("qty",0) or 0) for it in filtered)
        sum_unit_tot_qty = sum(float(it.get("unit_tot_qty",0) or 0) for it in filtered)
        sum_qty_times_unit = sum(
            float(it.get("qty",0) or 0) * float(it.get("unit_qty",0) or 0) for it in filtered
        )
        sum_totprc = sum(float(it.get("totprc",0) or 0) for it in filtered)
        sum_qty_times_price = sum(
            float(it.get("qty",0) or 0) * float(it.get("scsbd_prc",0) or 0) for it in filtered
        )
        print(f"    sum(qty)={sum_qty:.1f}")
        print(f"    sum(unit_tot_qty)={sum_unit_tot_qty:.1f}")
        print(f"    sum(qty*unit_qty)={sum_qty_times_unit:.1f}")
        print(f"    sum(totprc)={sum_totprc:.1f}")
        print(f"    sum(qty*scsbd_prc)={sum_qty_times_price:.1f}")

        # 첫 3건 raw 데이터
        print(f"    --- 샘플 3건 ---")
        for it in filtered[:3]:
            print(f"      qty={it.get('qty')}, unit_qty={it.get('unit_qty')}, "
                  f"unit_nm={it.get('unit_nm')}, unit_tot_qty={it.get('unit_tot_qty')}, "
                  f"scsbd_prc={it.get('scsbd_prc')}, totprc={it.get('totprc')}, "
                  f"pkg_nm={it.get('pkg_nm')}")
