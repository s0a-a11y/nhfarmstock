# -*- coding: utf-8 -*-
"""
감귤(대분류 06, 중분류 14)의 소분류코드 목록 조회 -> 하우스/노지 구분 코드 확인
"""
import os
import requests

KEY = os.environ["AT_API_KEY"]
BASE = "https://apis.data.go.kr/B552845/katCode"

def call_goods(lcode, mcode=None, page=1, num=300):
    params = {
        "serviceKey": KEY,
        "returnType": "json",
        "numOfRows": num,
        "pageNo": page,
        "cond[gds_lclsf_cd::EQ]": lcode,
        "selectable": "gds_lclsf_cd,gds_lclsf_nm,gds_mclsf_cd,gds_mclsf_nm,gds_sclsf_cd,gds_sclsf_nm",
    }
    if mcode:
        params["cond[gds_mclsf_cd::EQ]"] = mcode
    r = requests.get(f"{BASE}/goods", params=params, timeout=20)
    print(f"\n===== lclsf={lcode} mclsf={mcode} -> status {r.status_code} =====")
    try:
        data = r.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        total = data.get("response", {}).get("body", {}).get("totalCount")
        print(f"totalCount={total}, returned={len(items)}")
        seen = set()
        for it in items:
            key = (it.get("gds_mclsf_cd"), it.get("gds_mclsf_nm"), it.get("gds_sclsf_cd"), it.get("gds_sclsf_nm"))
            if key not in seen:
                seen.add(key)
                print(f"  중분류 {it.get('gds_mclsf_cd')}={it.get('gds_mclsf_nm')}  /  소분류 {it.get('gds_sclsf_cd')}={it.get('gds_sclsf_nm')}")
    except Exception as e:
        print("error:", e)
        print(r.text[:1000])

# 06 = 과일 대분류, 14 = 감귤류 중분류 (ITEM_CODES 기준)
call_goods("06", "14")
# 혹시 모르니 06 전체도 출력 (중분류 목록 확인용)
call_goods("06")
