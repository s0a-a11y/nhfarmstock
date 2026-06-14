# -*- coding: utf-8 -*-
"""
방울토마토(08-06)/양배추(10-04)에서 일부 시장의 필터후=0 건이 발생하는 원인 확인.
-> 해당 (대분류,중분류) 전체 거래의 gds_sclsf_cd 분포를 시장별로 출력하여,
   실제 사용되는 소분류 코드가 ITEM_CODES와 다른지 확인.
"""
import os
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

# (이름, 대분류, 중분류, 현재 설정된 소분류 필터)
TARGETS = [
    ("방울토마토", "08", "06", ["01"]),
    ("양배추", "10", "04", ["01"]),
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


for name, lclsf, mclsf, cur_filter in TARGETS:
    print(f"\n{'='*60}")
    print(f"▶ {name} (lclsf={lclsf}, mclsf={mclsf}, 현재필터={cur_filter})")
    print(f"{'='*60}")
    for mkey, mcode in MARKETS.items():
        items = fetch(mcode, lclsf, mclsf, yesterday)
        print(f"\n  [{mkey}] 전체 거래건수={len(items)}")
        if not items:
            continue
        # gds_sclsf_cd 분포
        counter = Counter((it.get("gds_sclsf_cd"), it.get("gds_sclsf_nm")) for it in items)
        for (code, nm), cnt in counter.most_common(10):
            # 해당 코드의 unit_qty, scsbd_prc 샘플도 같이 출력
            sample = next((it for it in items if it.get("gds_sclsf_cd") == code), {})
            print(f"    sclsf_cd={code} ({nm}): {cnt}건  "
                  f"| 샘플: unit_qty={sample.get('unit_qty')}, scsbd_prc={sample.get('scsbd_prc')}, "
                  f"pkg_nm={sample.get('pkg_nm')}")
