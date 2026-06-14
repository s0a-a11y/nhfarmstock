# -*- coding: utf-8 -*-
"""
전품목 일괄 검증 스크립트.

각 품목(ITEM_CODES)에 대해:
- 5개 시장에서 sclsf_filter 적용 후 거래건수
- unit_qty 분포 (시장 간 포장단위 불일치 여부)
- price_per_kg (가중평균)
- BOX_KG 환산 표시값 (garakSpecialKg 방식: price_per_kg 그대로가 화면 표시값)
- 5개 시장 표시값 기준 시장간 격차(gap%) = (max-min)/min*100

격차가 큰 품목(gap > 60%) 또는 필터후 0건 시장이 있는 품목을 ⚠️로 표시.
"""
import os
import time
import requests
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

KEY = os.environ["AT_API_KEY"]
BASE = "https://apis.data.go.kr/B552845/katOrigin"
CODE_BASE = "https://apis.data.go.kr/B552845/katCode"

MARKETS = {
    "garak": "110001", "daejeon": "250001", "busan": "210001",
    "gwangju": "240001", "daegu": "220001",
}
MKT_LABELS = {
    "garak": "가락시장(서울)", "daejeon": "오정도매시장(대전)",
    "busan": "엄궁도매시장(부산)", "gwangju": "각화도매시장(광주)",
    "daegu": "북부도매시장(대구)",
}
MKTS_K = list(MARKETS.keys())


# ──────────────────────────────────────────
# 0) 도매시장 코드 목록 검증 (katCode API)
# ──────────────────────────────────────────
print(f"{'='*90}")
print("도매시장 코드(whsl_mrkt_cd) 검증")
print(f"{'='*90}")
try:
    found = False
    for endpoint in ["markets", "market", "whsl", "whslMarkets", "whslMarket"]:
        r = requests.get(f"{CODE_BASE}/{endpoint}", params={
            "serviceKey": KEY, "returnType": "json", "numOfRows": 100, "pageNo": 1,
        }, timeout=20)
        try:
            data = r.json()
        except Exception:
            continue
        items = data.get("response", {}).get("body", {}).get("items", {})
        if not items:
            print(f"  (endpoint '{endpoint}': 결과 없음, status={r.status_code})")
            continue
        item = items.get("item", [])
        if isinstance(item, dict):
            item = [item]
        if item:
            print(f"  -> endpoint '{endpoint}' 사용, 결과 {len(item)}건")
            print(f"  샘플 키: {list(item[0].keys())}")
            found = True
            code_map = {}
            for it in item:
                code = it.get("whsl_mrkt_cd") or it.get("mrkt_cd") or it.get("cd")
                nm = it.get("whsl_mrkt_nm") or it.get("mrkt_nm") or it.get("nm")
                code_map[code] = nm
                if code in MARKETS.values():
                    mkey = [k for k, v in MARKETS.items() if v == code][0]
                    expected = MKT_LABELS[mkey]
                    match = "OK" if expected.split("(")[0] in (nm or "") else "⚠️ 불일치"
                    print(f"    {code} -> API: {nm}  |  코드설정: {mkey}={expected}  [{match}]")
            for mkey, code in MARKETS.items():
                if code not in code_map:
                    print(f"    ⚠️ {mkey}={code} 코드가 목록에 없음!")
            break
    if not found:
        print("  ⚠️ 시장코드 목록 엔드포인트를 찾지 못함. 수동 검증 필요.")
except Exception as e:
    print(f"  ⚠️ 시장코드 조회 실패: {e}")

print()

ITEM_CODES = {
    "수미감자":   ("05", "01", ["01"]),
    "두백감자":   ("05", "01", ["13"]),
    "홍감자":     ("05", "01", ["18"]),
    "후지사과":   ("06", "01", ["03"]),
    "홍로사과":   ("06", "01", ["17"]),
    "감홍사과":   ("06", "01", ["29"]),
    "배":         ("06", "02", ["01"]),
    "거봉포도":   ("06", "03", ["02"]),
    "캠벨포도":   ("06", "03", ["01"]),
    "샤인머스켓": ("06", "03", ["36"]),
    "백도복숭아": ("06", "04", ["11", "55", "F4", "83", "62", "98"]),
    "황도복숭아": ("06", "04", ["92"]),
    "천도복숭아": ("06", "04", ["47", "E7", "E8", "B4"]),
    "단감":       ("06", "05", ["01"]),
    "태추단감":   ("06", "05", ["22"]),
    "감귤(하우스)": ("06", "14", ["05"]),
    "감귤(노지)":   ("06", "14", ["00", "01", "02", "03"]),
    "수박":       ("08", "01", ["00"]),
    "일반토마토": ("08", "03", ["03"]),
    "딸기":       ("08", "04", ["00"]),
    "방울토마토": ("08", "06", ["01"]),
    "백오이":     ("09", "01", ["02"]),
    "취청오이":   ("09", "01", ["01"]),
    "가시오이":   ("09", "01", ["03"]),
    "애호박":     ("09", "02", ["01"]),
    "쥬키니":     ("09", "02", ["02"]),
    "단호박":     ("09", "02", ["05"]),
    "배추":       ("10", "01", ["00"]),
    "양배추":     ("10", "04", ["01"]),
    "적상추":     ("10", "05", ["02"]),
    "청상추":     ("10", "05", ["01"]),
    "포기상추":   ("10", "05", ["03", "04"]),
    "무":         ("11", "01", ["00"]),
    "양파":       ("12", "01", ["01"]),
    "대파":       ("12", "02", ["01"]),
    "풋고추":     ("12", "05", ["05"]),
    "청양고추":   ("12", "05", ["01"]),
}

# (lclsf, mclsf) -> [품목명...] 그룹핑 (API 호출 최소화)
GROUPS = {}
for nm, (l, mc, _) in ITEM_CODES.items():
    GROUPS.setdefault((l, mc), []).append(nm)


def fetch(whsl_mrkt_cd, lclsf, mclsf, ymd, retries=2):
    params = {
        "serviceKey": KEY, "returnType": "json", "numOfRows": 1000, "pageNo": 1,
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[gds_lclsf_cd::EQ]": lclsf,
        "cond[gds_mclsf_cd::EQ]": mclsf,
        "cond[trd_clcln_ymd::EQ]": ymd,
        "selectable": "gds_sclsf_cd,unit_qty,unit_nm,qty,scsbd_prc,totprc",
    }
    for attempt in range(retries + 1):
        try:
            r = requests.get(f"{BASE}/trades", params=params, timeout=25)
            data = r.json()
            items = data.get("response", {}).get("body", {}).get("items", {})
            if not items:
                return []
            arr = items.get("item", [])
            return [arr] if isinstance(arr, dict) else arr
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            print(f"  ⚠️ fetch 실패 ({whsl_mrkt_cd},{lclsf}-{mclsf}): {e}")
            return None


def calc(items, sclsf_filter):
    valid = []
    for it in items:
        if sclsf_filter is not None and it.get("gds_sclsf_cd", "") not in sclsf_filter:
            continue
        try:
            qty = float(it.get("qty", 0) or 0)
            price = float(it.get("scsbd_prc", 0) or 0)
            unit_qty = float(it.get("unit_qty", 0) or 0)
        except (TypeError, ValueError):
            continue
        if qty <= 0 or price <= 0 or unit_qty <= 0:
            continue
        valid.append((qty, price, unit_qty))
    if not valid:
        return None
    total_qty_kg = sum(q * u for q, _, u in valid)
    total_amount = sum(q * u * p for q, p, u in valid)
    price_per_kg = total_amount / total_qty_kg
    unit_qtys = sorted(set(u for _, _, u in valid))
    return {
        "n": len(valid),
        "price_per_kg": price_per_kg,
        "unit_qtys": unit_qtys,
        "qty_kg": total_qty_kg,
    }


# 캐시: (lclsf, mclsf, mkey) -> items
cache = {}

results = {}  # name -> {mkey: calc_result}
for (lclsf, mclsf), names in GROUPS.items():
    for mkey, mcode in MARKETS.items():
        key = (lclsf, mclsf, mkey)
        items = fetch(mcode, lclsf, mclsf, yesterday)
        cache[key] = items if items is not None else []
        time.sleep(0.08)

for nm, (lclsf, mclsf, sclsf_filter) in ITEM_CODES.items():
    results[nm] = {}
    for mkey in MKTS_K:
        items = cache.get((lclsf, mclsf, mkey), [])
        c = calc(items, sclsf_filter)
        if c:
            results[nm][mkey] = c

print(f"{'='*90}")
print(f"전품목 검증 ({yesterday} 기준)")
print(f"{'='*90}")

flagged = []
for nm in ITEM_CODES:
    mdata = results.get(nm, {})
    missing = [mk for mk in MKTS_K if mk not in mdata]
    kg_prices = {mk: mdata[mk]["price_per_kg"] for mk in mdata}
    gap = None
    if len(kg_prices) >= 2:
        vals = list(kg_prices.values())
        gap = round((max(vals) - min(vals)) / min(vals) * 100)

    # unit_qty 불일치 체크 (시장 간)
    all_unit_qtys = set()
    for mk in mdata:
        all_unit_qtys.update(mdata[mk]["unit_qtys"])
    unit_mismatch = len(all_unit_qtys) > 1

    issues = []
    if missing:
        issues.append(f"데이터없음:{missing}")
    if gap is not None and gap > 60:
        issues.append(f"격차{gap}%")
    if unit_mismatch:
        issues.append(f"unit_qty다양:{sorted(all_unit_qtys)}")

    tag = "⚠️ " if issues else "   "
    print(f"{tag}{nm:12s} | ", end="")
    for mk in MKTS_K:
        if mk in mdata:
            print(f"{mk}={mdata[mk]['price_per_kg']:8.1f}", end="  ")
        else:
            print(f"{mk}={'N/A':>8s}", end="  ")
    gap_str = f"gap={gap}%" if gap is not None else "gap=N/A"
    print(f"| {gap_str}", end="")
    if issues:
        print(f"  <-- {', '.join(issues)}")
        flagged.append((nm, issues))
    else:
        print()

print(f"\n{'='*90}")
print(f"⚠️ 점검 필요 품목: {len(flagged)}개")
for nm, issues in flagged:
    print(f"  - {nm}: {', '.join(issues)}")
