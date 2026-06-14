# -*- coding: utf-8 -*-
"""
최종 점검: 데이터없음/이상치로 플래그된 품목들의 katCode 소분류 목록을
일괄 조회하여, 현재 ITEM_CODES의 sclsf_filter가 올바른지 확인.

대상 (중분류 단위로 묶음):
- 두백감자/홍감자 (05-01)
- 홍로사과/감홍사과 (06-01)
- 거봉포도/캠벨포도/샤인머스켓 (06-03)
- 백도복숭아/황도복숭아/천도복숭아 (06-04)
- 단감/태추단감 (06-05)
- 수박 (08-01)
- 일반토마토 (08-03)
- 딸기 (08-04)
- 방울토마토 (08-06)
- 단호박 (09-02)
- 배추 (10-01)
- 적상추/청상추/포기상추 (10-05)
- 무 (11-01)
- 풋고추/청양고추 (12-05)
"""
import os
import requests

KEY = os.environ["AT_API_KEY"]
BASE = "https://apis.data.go.kr/B552845/katCode"

# (lclsf, mclsf, 설명)
TARGETS = [
    ("05", "01", "감자류"),
    ("06", "01", "사과"),
    ("06", "03", "포도"),
    ("06", "04", "복숭아"),
    ("06", "05", "단감"),
    ("08", "01", "수박"),
    ("08", "03", "토마토"),
    ("08", "04", "딸기"),
    ("08", "06", "방울토마토"),
    ("09", "02", "호박류"),
    ("10", "01", "배추"),
    ("10", "05", "상추"),
    ("11", "01", "무"),
    ("12", "05", "고추"),
]


def call_goods(lcode, mcode, num=300):
    params = {
        "serviceKey": KEY,
        "returnType": "json",
        "numOfRows": num,
        "pageNo": 1,
        "cond[gds_lclsf_cd::EQ]": lcode,
        "cond[gds_mclsf_cd::EQ]": mcode,
        "selectable": "gds_lclsf_cd,gds_lclsf_nm,gds_mclsf_cd,gds_mclsf_nm,gds_sclsf_cd,gds_sclsf_nm",
    }
    r = requests.get(f"{BASE}/goods", params=params, timeout=20)
    try:
        data = r.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        return items
    except Exception as e:
        print(f"  error: {e}, {r.text[:300]}")
        return []


for lcode, mcode, label in TARGETS:
    print(f"\n{'='*60}")
    print(f"▶ {label} (lclsf={lcode}, mclsf={mcode})")
    print(f"{'='*60}")
    items = call_goods(lcode, mcode)
    seen = set()
    for it in items:
        key = (it.get("gds_sclsf_cd"), it.get("gds_sclsf_nm"))
        if key not in seen:
            seen.add(key)
    for code, nm in sorted(seen):
        print(f"  소분류 {code} = {nm}")
