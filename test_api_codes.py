# -*- coding: utf-8 -*-
"""
data.go.kr 'katCode' API 테스트
- 도매시장코드 목록 (wholesaleMarkets)
- 품목 대분류 코드 목록 (goods, 대분류만)
실행 결과는 GitHub Actions 로그에 출력됩니다.
"""
import os
import requests
import json

KEY = os.environ["AT_API_KEY"]  # Decoding 키 (URL 인코딩 없이 그대로)
BASE = "https://apis.data.go.kr/B552845/katCode"

def call(path, extra_params=None, num=100):
    params = {
        "serviceKey": KEY,
        "returnType": "json",
        "numOfRows": num,
        "pageNo": 1,
    }
    if extra_params:
        params.update(extra_params)
    r = requests.get(f"{BASE}/{path}", params=params, timeout=20)
    print(f"\n===== {path} -> status {r.status_code} =====")
    try:
        data = r.json()
        print(json.dumps(data, ensure_ascii=False, indent=2)[:6000])
    except Exception as e:
        print("JSON parse error:", e)
        print(r.text[:2000])

# 1) 전국 도매시장 코드 목록
call("wholesaleMarkets", num=200)

# 2) 품목 대분류 코드 목록 (소/중분류 없이 전체 조회 시도)
call("goods", num=300)
