# -*- coding: utf-8 -*-
"""
data.go.kr 'katCode' API 테스트 (4차 - 최종)
- 06(과실류) 3페이지: 감귤, 딸기, 참외, 수박 등 확인
- 08 ~ 12 대분류 확인: 채소류(배추, 무, 양파 등) 대분류 정체 추적
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
    try:
        r = requests.get(f"{BASE}/goods", params=params, timeout=20)
        print(f"\n===== lclsf={lcode} page={page} -> status {r.status_code} =====")
        data = r.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        total = data.get("response", {}).get("body", {}).get("totalCount")
        print(f"totalCount={total}, returned={len(items)}")
        if items:
            lname = items[0].get("gds_lclsf_nm")
            print(f"대분류명: {lname}")
        seen = set()
        # 상위 30개만 샘플링 출력하여 로그가 끊기지 않게 방지 (대분류 정체 파악용)
        for it in items[:40]:
            key = (it.get("gds_mclsf_cd"), it.get("gds_mclsf_nm"))
            if key not in seen:
                seen.add(key)
                print(f"  중분류 {it.get('gds_mclsf_cd')}={it.get('gds_mclsf_nm')}")
    except Exception as e:
        print(f"error on {lcode}: {e}")

# 1. 06(과실류) 3페이지 - 남은 과일류 품목 싹쓸이
call_goods("06", page=3)

# 2. 채소류 대분류 찾기 탐험 (08번부터 12번까지 순회)
for code in ["08", "09", "10", "11", "12"]:
    call_goods(code, page=1)
