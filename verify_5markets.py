# -*- coding: utf-8 -*-
"""
5개 시장코드가 모두 정상 데이터를 반환하는지 + 시장명이 맞는지 한 번에 검증.
양파(12-01)와 샤인머스켓(06-03-36)으로 테스트.
"""
import os
import requests
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

KEY = os.environ["AT_API_KEY"]
BASE = "https://apis.data.go.kr/B552845/katOrigin"

MARKETS = {
    "garak": "110001", "daejeon": "250001", "busan": "210001",
    "gwangju": "240004", "daegu": "220001",
}


def fetch(whsl_mrkt_cd, lclsf, mclsf, sclsf, ymd):
    params = {
        "serviceKey": KEY, "returnType": "json", "numOfRows": 1000, "pageNo": 1,
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[gds_lclsf_cd::EQ]": lclsf,
        "cond[gds_mclsf_cd::EQ]": mclsf,
        "cond[trd_clcln_ymd::EQ]": ymd,
        "selectable": "whsl_mrkt_nm,gds_sclsf_cd,unit_qty,qty,scsbd_prc",
    }
    r = requests.get(f"{BASE}/trades", params=params, timeout=25)
    data = r.json()
    items = data.get("response", {}).get("body", {}).get("items", {})
    if not items:
        return []
    arr = items.get("item", [])
    arr = [arr] if isinstance(arr, dict) else arr
    if sclsf:
        arr = [it for it in arr if it.get("gds_sclsf_cd") in sclsf]
    return arr


print(f"기준일: {yesterday}\n")

print("="*60)
print("양파 (12-01-01)")
print("="*60)
for mkey, code in MARKETS.items():
    items = fetch(code, "12", "01", ["01"], yesterday)
    nm = items[0].get("whsl_mrkt_nm") if items else "N/A"
    qty_kg = sum(float(it.get("qty",0) or 0)*float(it.get("unit_qty",0) or 0) for it in items)
    print(f"  {mkey:8s} (code={code}): whsl_mrkt_nm={nm}, 건수={len(items)}, 총물량={qty_kg:.1f}kg")

print()
print("="*60)
print("샤인머스켓 (06-03-36)")
print("="*60)
for mkey, code in MARKETS.items():
    items = fetch(code, "06", "03", ["36"], yesterday)
    nm = items[0].get("whsl_mrkt_nm") if items else "N/A"
    if items:
        total_qty = sum(float(it.get("qty",0) or 0) for it in items)
        total_kg = sum(float(it.get("qty",0) or 0)*float(it.get("unit_qty",0) or 0) for it in items)
        total_amt = sum(float(it.get("qty",0) or 0)*float(it.get("unit_qty",0) or 0)*float(it.get("scsbd_prc",0) or 0) for it in items)
        ppk = total_amt/total_kg if total_kg else 0
        print(f"  {mkey:8s} (code={code}): whsl_mrkt_nm={nm}, 건수={len(items)}, price_per_kg={ppk:.1f}")
    else:
        print(f"  {mkey:8s} (code={code}): 데이터 없음")
