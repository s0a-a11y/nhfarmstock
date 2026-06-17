# -*- coding: utf-8 -*-
"""
배(梨)의 소분류코드(gds_sclsf_cd)별 품종명을 확인.
selectable에 gds_sclsf_nm(소분류명) 필드를 추가해 코드-품종명 매핑을 직접 확인.
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


def fetch(whsl_mrkt_cd, lclsf, mclsf, ymd):
    params = {
        "serviceKey": KEY, "returnType": "json", "numOfRows": 1000, "pageNo": 1,
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[gds_lclsf_cd::EQ]": lclsf,
        "cond[gds_mclsf_cd::EQ]": mclsf,
        "cond[trd_clcln_ymd::EQ]": ymd,
        "selectable": "gds_sclsf_cd,gds_sclsf_nm,unit_qty,qty,scsbd_prc,pkg_nm",
    }
    r = requests.get(f"{BASE}/trades", params=params, timeout=25)
    data = r.json()
    items = data.get("response", {}).get("body", {}).get("items", {})
    if not items:
        return []
    arr = items.get("item", [])
    return [arr] if isinstance(arr, dict) else arr


print(f"기준일: {yesterday}")
print("="*60)
print("배 (06-02) 가락시장 - 소분류코드별 품종명")
print("="*60)
items = fetch("110001", "06", "02", yesterday)
print(f"총 건수: {len(items)}")
combo = Counter((it.get("gds_sclsf_cd"), it.get("gds_sclsf_nm")) for it in items)
for (code, nm), cnt in sorted(combo.items(), key=lambda x: -x[1]):
    print(f"  코드={code}  품종명={nm}  건수={cnt}")
