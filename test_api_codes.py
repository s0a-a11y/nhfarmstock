# -*- coding: utf-8 -*-
"""
data.go.kr 'katCode' API 테스트 (5차 - 핵심 채소/과일 코드 전수 추출)
- 발견된 핵심 대분류들(06, 08, 09, 10, 11, 12)의 모든 페이지를 순회하며 
  중분류와 소분류 코드를 완전하게 추출합니다.
"""
import os
import requests

KEY = os.environ["AT_API_KEY"]
BASE = "https://apis.data.go.kr/B552845/katCode"

def fetch_all_goods_for_category(lcode):
    page = 1
    num = 300
    all_items = []
    lname = ""
    
    print(f"\n==========================================")
    print(f"▶ 대분류 코드 [{lcode}] 전수 조사 시작")
    print(f"==========================================")
    
    while True:
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
            if r.status_code != 200:
                print(f"  [Error] status {r.status_code} on page {page}")
                break
                
            data = r.json()
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            total = data.get("response", {}).get("body", {}).get("totalCount", 0)
            
            if not items:
                break
                
            if page == 1 and items:
                lname = items[0].get("gds_lclsf_nm")
                print(f"대분류명: {lname} (총 데이터 수: {total}건)")
                
            all_items.extend(items)
            
            # 모든 데이터를 다 가져왔으면 루프 종료
            if len(all_items) >= total or len(items) < num:
                break
                
            page += 1
        except Exception as e:
            print(f"  [Exception] {e}")
            break

    # 중분류-소분류 정렬 및 출력
    seen = set()
    unique_outputs = []
    for it in all_items:
        m_cd = it.get("gds_mclsf_cd")
        m_nm = it.get("gds_mclsf_nm")
        s_cd = it.get("gds_sclsf_cd")
        s_nm = it.get("gds_sclsf_nm")
        
        key = (m_cd, m_nm, s_cd, s_nm)
        if key not in seen:
            seen.add(key)
            unique_outputs.append(f"  중분류 {m_cd}={m_nm}  /  소분류 {s_cd}={s_nm}")
            
    # 로그 길이 안 끊기도록 핵심 정보만 콤팩트하게 출력
    print(f"-> 중/소분류 고유 조합 개수: {len(unique_outputs)}개")
    for out in unique_outputs:
        print(out)

# 타겟 대분류 리스트 (과실류, 과일과채류, 과채류, 엽경채류, 근채류, 조미채소류)
target_categories = ["06", "08", "09", "10", "11", "12"]

for cat in target_categories:
    fetch_all_goods_for_category(cat)
