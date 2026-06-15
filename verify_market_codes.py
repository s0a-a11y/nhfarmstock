# -*- coding: utf-8 -*-
"""
시장코드(whsl_mrkt_cd) 실제 명칭 검증.

katOrigin/trades API의 selectable에 시장명 관련 필드(whsl_mrkt_nm 등)를
포함시켜 직접 응답에서 시장명을 확인. 또한 각 후보 코드로 양파(전국 주요
거래품목)를 조회해 실제로 데이터가 들어오는지, 거래량 패턴이 어느 지역과
일치하는지 확인.

추가로 광주 지역의 후보 시장코드들을 여러 개 테스트하여 각화/서부 중
어느 쪽이 현재 코드(240001)에 해당하는지 식별.
"""
import os
import requests
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

KEY = os.environ["AT_API_KEY"]
BASE = "https://apis.data.go.kr/B552845/katOrigin"

# 현재 설정된 코드들
CURRENT = {
    "garak(가락)": "110001",
    "daejeon(오정)": "250001",
    "busan(엄궁)": "210001",
    "gwangju(각화?)": "240001",
    "daegu(북부)": "220001",
}

# 광주 인근 후보 코드 (10xxxx~30xxxx 범위에서 추정 - 일반적으로 시도별 앞 2자리 코드 패턴)
GWANGJU_CANDIDATES = {
    "240001": "현재 설정값",
    "240002": "후보2",
    "230001": "후보3",
    "230002": "후보4",
}


def fetch(whsl_mrkt_cd, lclsf, mclsf, sclsf, ymd):
    params = {
        "serviceKey": KEY, "returnType": "json", "numOfRows": 1000, "pageNo": 1,
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[gds_lclsf_cd::EQ]": lclsf,
        "cond[gds_mclsf_cd::EQ]": mclsf,
        "cond[trd_clcln_ymd::EQ]": ymd,
        "selectable": "whsl_mrkt_cd,whsl_mrkt_nm,whsl_cmp_nm,gds_sclsf_cd,unit_qty,qty,scsbd_prc,totprc,pkg_nm",
    }
    r = requests.get(f"{BASE}/trades", params=params, timeout=25)
    try:
        data = r.json()
    except Exception as e:
        print(f"    error parsing: {e}, raw={r.text[:300]}")
        return []
    items = data.get("response", {}).get("body", {}).get("items", {})
    if not items:
        return []
    arr = items.get("item", [])
    return [arr] if isinstance(arr, dict) else arr


print("="*70)
print("1) 현재 설정된 5개 시장코드의 whsl_mrkt_nm 필드 확인 (양파 12-01)")
print("="*70)
for label, code in CURRENT.items():
    items = fetch(code, "12", "01", None, yesterday)
    if items:
        sample = items[0]
        print(f"  {label} (code={code}): 건수={len(items)}, "
              f"whsl_mrkt_nm={sample.get('whsl_mrkt_nm')}, "
              f"whsl_mrkt_cd(응답)={sample.get('whsl_mrkt_cd')}, "
              f"whsl_cmp_nm={sample.get('whsl_cmp_nm')}")
    else:
        print(f"  {label} (code={code}): 데이터 없음")

print()
print("="*70)
print("2) 광주 지역 후보 코드 추가 확인 (양파 12-01)")
print("="*70)
for code, label in GWANGJU_CANDIDATES.items():
    items = fetch(code, "12", "01", None, yesterday)
    if items:
        sample = items[0]
        print(f"  {code} ({label}): 건수={len(items)}, "
              f"whsl_mrkt_nm={sample.get('whsl_mrkt_nm')}, "
              f"whsl_cmp_nm={sample.get('whsl_cmp_nm')}")
    else:
        print(f"  {code} ({label}): 데이터 없음")
