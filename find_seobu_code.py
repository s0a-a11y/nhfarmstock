# -*- coding: utf-8 -*-
"""
광주서부농수산물도매시장의 whsl_mrkt_cd 탐색.
각화=240001로 확인됨. 인근 코드 범위(24xxxx) 및 다른 일반적 패턴 시도.
"""
import os
import requests
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

KEY = os.environ["AT_API_KEY"]
BASE = "https://apis.data.go.kr/B552845/katOrigin"

# 각화=240001 확인됨. 같은 광주 관할 내 다른 시장 코드 후보들.
# 패턴: 첫 2자리가 광역시도 코드(24=광주 추정), 뒤 4자리가 시장 식별자
CANDIDATES = [
    "240003", "240004", "240005", "240010",
    "240011", "240012", "240020", "240100",
    "241001", "242001", "243001",
    "245001", "246001", "247001", "248001", "249001",
    "260001", "270001", "280001", "290001",
]


def fetch(whsl_mrkt_cd, lclsf, mclsf, ymd):
    params = {
        "serviceKey": KEY, "returnType": "json", "numOfRows": 50, "pageNo": 1,
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[gds_lclsf_cd::EQ]": lclsf,
        "cond[gds_mclsf_cd::EQ]": mclsf,
        "cond[trd_clcln_ymd::EQ]": ymd,
        "selectable": "whsl_mrkt_cd,whsl_mrkt_nm,qty,scsbd_prc",
    }
    r = requests.get(f"{BASE}/trades", params=params, timeout=25)
    try:
        data = r.json()
    except Exception as e:
        return None, str(e)
    items = data.get("response", {}).get("body", {}).get("items", {})
    if not items:
        return [], None
    arr = items.get("item", [])
    return ([arr] if isinstance(arr, dict) else arr), None


print("="*60)
print("광주서부 코드 탐색 (양파 12-01, 어제자)")
print("="*60)
for code in CANDIDATES:
    items, err = fetch(code, "12", "01", yesterday)
    if err:
        print(f"  {code}: error {err}")
    elif items:
        nm = items[0].get("whsl_mrkt_nm")
        print(f"  {code}: 건수={len(items)}, whsl_mrkt_nm={nm}")
    else:
        print(f"  {code}: 데이터 없음")
