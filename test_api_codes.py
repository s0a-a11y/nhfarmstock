# -*- coding: utf-8 -*-
"""
data.go.kr 'katCode' API 테스트 (4차)
- 04, 12, 13 대분류 조회 (양파/대파/고추류 = 양념채소류 추정)
"""
import os
import requests

KEY = os.environ["AT_API_KEY"]
BASE = "https://apis.data.go.kr/B552845/katCode"

def call_goods(lcode, page=1, num=300):
    params = {
        "serviceKey": KEY,
        "returnType": "json",
        "numOfRows": num,
        "pageNo": page,
        "cond[gds_lclsf_cd::EQ]": lcode,
        "selectable": "gds_lclsf_cd,gds_lclsf_nm,gds_mclsf_cd,gds_mclsf_nm,gds_sclsf_cd,gds_sclsf_nm",
    }
    r = requests.get(f"{BASE}/goods", params=params, timeout=20)
    print(f"\n===== lclsf={lcode} page={page} -> status {r.status_code} =====")
    try:
        data = r.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        total = data.get("response", {}).get("body", {}).get("totalCount")
        print(f"totalCount={total}, returned={len(items)}")
        if items:
            lname = items[0].get("gds_lclsf_nm")
            print(f"대분류명: {lname}")
        seen = set()
        for it in items:
            key = (it.get("gds_mclsf_cd"), it.get("gds_mclsf_nm"), it.get("gds_sclsf_cd"), it.get("gds_sclsf_nm"))
            if key not in seen:
                seen.add(key)
                print(f"  중분류 {it.get('gds_mclsf_cd')}={it.get('gds_mclsf_nm')}  /  소분류 {it.get('gds_sclsf_cd')}={it.get('gds_sclsf_nm')}")
    except Exception as e:
        print("error:", e)
        print(r.text[:1000])

for lcode in ["04","12","13"]:
    call_goods(lcode)
