# -*- coding: utf-8 -*-
"""
NH_Farm_Stock 일일 데이터 갱신 (실제 API 연동판)

흐름:
1. data.go.kr 'katOrigin/trades' API로 5개 시장 x 38개 품목의
   실제 반입량(qty)과 경락 단가(scsbd_prc)를 조회 (조회일=어제, KST)
2. 조회 성공한 품목 -> 실데이터로 prices/vol 교체, chg는 (신규-기존)/기존*100 로 계산
3. 조회 실패/데이터 없음 품목 -> 기존 방식(소폭 랜덤 변동)으로 보완
4. API 키 미설정 시 전체 랜덤 변동 (기존 동작과 동일, 안전장치)
"""
import os
import re
import time
import random
import shutil
from datetime import datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
today = now.strftime("%Y-%m-%d")
yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
random.seed(f"{today}-{'AM' if now.hour < 10 else 'PM'}")

KEY = os.environ.get("AT_API_KEY", "")
BASE = "https://apis.data.go.kr/B552845/katOrigin"
MKTS_K = ["garak", "daejeon", "busan", "gwangju", "daegu"]

MARKETS = {
    "garak": "110001", "daejeon": "250001", "busan": "210001",
    "gwangju": "240004", "daegu": "220001",
}

# 품목명 -> (대분류, 중분류, [소분류코드...] or None=중분류 전체)
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
    "수박":       ("08", "01", ["01"]),
    "일반토마토": ("08", "03", ["01", "03"]),
    "딸기":       ("08", "04", ["00"]),
    "방울토마토": ("08", "06", ["01", "02", "03"]),
    "백오이":     ("09", "01", ["02"]),
    "취청오이":   ("09", "01", ["01"]),
    "가시오이":   ("09", "01", ["03"]),
    "애호박":     ("09", "02", ["01"]),
    "쥬키니":     ("09", "02", ["02"]),
    "단호박":     ("09", "02", ["05"]),
    "배추":       ("10", "01", ["00", "01", "02"]),
    "양배추":     ("10", "04", ["01"]),
    "적상추":     ("10", "05", ["02"]),
    "청상추":     ("10", "05", ["01"]),
    "포기상추":   ("10", "05", ["03", "04"]),
    "무":         ("11", "01", ["00", "01", "02"]),
    "양파":       ("12", "01", ["01"]),
    "대파":       ("12", "02", ["01"]),
    "풋고추":     ("12", "05", ["05"]),
    "청양고추":   ("12", "05", ["01"]),
}

GROUPS = {}
for nm, (l, mc, _) in ITEM_CODES.items():
    GROUPS.setdefault((l, mc), []).append(nm)


def fetch_trades(whsl_mrkt_cd, lclsf, mclsf, ymd, retries=2):
    params = {
        "serviceKey": KEY, "returnType": "json", "numOfRows": 1000, "pageNo": 1,
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[gds_lclsf_cd::EQ]": lclsf,
        "cond[gds_mclsf_cd::EQ]": mclsf,
        "cond[trd_clcln_ymd::EQ]": ymd,
        "selectable": "gds_sclsf_cd,unit_qty,unit_nm,qty,scsbd_prc",
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


def aggregate(items, sclsf_filter):
    """반입량(kg합계)과 가중평균 '포장단위당 낙찰가'(scsbd_prc, 원/포장)를 계산.
    또한 가중평균 unit_qty(포장당 kg)도 함께 반환하여, 우리 BOX_KG와의
    환산 비율을 계산할 수 있게 한다. 데이터 없으면 None.

    이상치 제거: unit_qty(포장단위)별로 그룹화하여 price_per_kg을 구하고,
    거래건수가 전체의 5% 미만이면서 price_per_kg이 전체 중앙값(median) 대비
    1.5배 이상/0.67배 이하인 그룹은 소수 특수거래(이상치)로 간주해 제외한다.
    예: 감귤(하우스) 가락시장의 8kg/9.6kg 파렛트 1~2건이 price_per_kg을
    12,500~17,500원까지 왜곡시키는 케이스 방지."""
    valid = []
    for it in items:
        if sclsf_filter is not None and it.get("gds_sclsf_cd", "") not in sclsf_filter:
            continue
        try:
            qty = float(it.get("qty", 0) or 0)          # 거래 건수(포장 개수)
            price = float(it.get("scsbd_prc", 0) or 0)  # 포장 1개당 낙찰가(원)
            unit_qty = float(it.get("unit_qty", 0) or 0)  # 포장 1개당 중량(kg 등)
        except (TypeError, ValueError):
            continue
        if qty <= 0 or price <= 0 or unit_qty <= 0:
            continue
        valid.append((qty, price, unit_qty))
    if not valid:
        return None

    # unit_qty별 그룹화
    groups = {}
    for q, p, u in valid:
        g = groups.setdefault(u, {"qty": 0.0, "amount": 0.0})
        g["qty"] += q
        g["amount"] += q * p

    total_qty_all = sum(g["qty"] for g in groups.values())
    # 그룹별 price_per_kg
    group_ppk = {u: g["amount"] / (g["qty"] * u) for u, g in groups.items()}
    ppk_values = sorted(group_ppk.values())
    median_ppk = ppk_values[len(ppk_values) // 2]

    # 이상치 그룹 제외 (단, 모든 그룹이 제외 대상이면 전부 유지)
    kept = {}
    for u, g in groups.items():
        ppk = group_ppk[u]
        small = g["qty"] / total_qty_all < 0.05 if total_qty_all > 0 else False
        far = ppk > median_ppk * 1.5 or ppk < median_ppk / 1.5
        if small and far:
            continue
        kept[u] = g
    if not kept:
        kept = groups

    total_qty = sum(g["qty"] for g in kept.values())            # 총 포장 개수
    total_qty_kg = sum(g["qty"] * u for u, g in kept.items())   # 총 중량(kg)
    total_amount = sum(g["amount"] for g in kept.values())      # 총 거래금액(원)
    avg_price_per_pkg = total_amount / total_qty       # 원/포장(가중평균)
    avg_unit_qty = total_qty_kg / total_qty            # kg/포장(가중평균)
    return {
        "qty_kg": total_qty_kg,
        "avg_price_per_pkg": avg_price_per_pkg,
        "avg_unit_qty": avg_unit_qty,
    }


# ──────────────────────────────────────────
# 0) BOX_KG 미리 로드 (디버그 출력용)
# ──────────────────────────────────────────
with open("index.html", "r", encoding="utf-8") as f:
    _html_preview = f.read()
_box_m = re.search(r"const BOX_KG=\{(.*?)\};", _html_preview, re.S)
BOX_KG_DEBUG = {k: float(v) for k, v in re.findall(r"'([^']+)':([\d.]+)", _box_m.group(1))} if _box_m else {}

# ──────────────────────────────────────────
# 1) API에서 실데이터 수집
# ──────────────────────────────────────────
results = {}
if KEY:
    api_ok = api_fail = 0
    for (lclsf, mc), names in GROUPS.items():
        for mkey, mcode in MARKETS.items():
            items = fetch_trades(mcode, lclsf, mc, yesterday)
            if items is None:
                api_fail += 1
                continue
            api_ok += 1
            for nm in names:
                _, _, sclsf_filter = ITEM_CODES[nm]
                agg = aggregate(items, sclsf_filter)
                if agg:
                    results.setdefault(nm, {})[mkey] = agg
            time.sleep(0.1)
    print(f"▶ API 호출: 성공 {api_ok} / 실패 {api_fail}  |  데이터 확보 품목: {len(results)}/{len(ITEM_CODES)}")

    # 디버그: 품목별 가락시장 API 원본 단위/가격 출력 (단위 환산 검증용)
    print("--- 디버그: 가락(garak) 기준 API 원시값 (전 품목) ---")
    for nm, mdata in results.items():
        g = mdata.get("garak")
        if g:
            box_kg = BOX_KG_DEBUG.get(nm, "?")
            ppk = g['avg_price_per_pkg'] / g['avg_unit_qty'] if g['avg_unit_qty'] else 0
            print(f"  {nm}: avg_unit_qty={g['avg_unit_qty']:.2f}, "
                  f"avg_price_per_pkg={g['avg_price_per_pkg']:.1f}, "
                  f"price_per_kg={ppk:.1f}, qty_kg={g['qty_kg']:.1f}, BOX_KG={box_kg}")
else:
    print("⚠️ AT_API_KEY 미설정 — 전체 랜덤 변동 모드")

# ──────────────────────────────────────────
# 2) index.html 로드 + 단위 정보 추출
# ──────────────────────────────────────────
with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

box_kg_m = re.search(r"const BOX_KG=\{(.*?)\};", html, re.S)
BOX_KG = {k: float(v) for k, v in re.findall(r"'([^']+)':([\d.]+)", box_kg_m.group(1))} if box_kg_m else {}

ITEM_BLOCK = re.compile(
    r"(\{name:'([^']+)',(?:(?!prices:\{|\{name:').)*?prices:\{)garak:(\d+),daejeon:(\d+),busan:(\d+),gwangju:(\d+),daegu:(\d+)"
    r"(\},\s*chg:\{)garak:([-\d.]+),daejeon:([-\d.]+),busan:([-\d.]+),gwangju:([-\d.]+),daegu:([-\d.]+)"
    r"(\},\s*vol:\{)garak:(\d+(?:\.\d+)?),daejeon:(\d+(?:\.\d+)?),busan:(\d+(?:\.\d+)?),gwangju:(\d+(?:\.\d+)?),daegu:(\d+(?:\.\d+)?)(\})",
    re.S,
)


def process(m):
    name = m.group(2)
    old_prices = [int(m.group(i)) for i in (3, 4, 5, 6, 7)]
    old_vols = [float(m.group(i)) for i in (15, 16, 17, 18, 19)]

    market_data = results.get(name)
    if market_data:
        # 우리 사이트 기준 "박스(포장)당 kg" (BOX_KG). 수박은 18kg(2입) 박스 기준.
        our_box_kg = BOX_KG.get(name, 10)
        new_prices, new_vols = [], []
        has_agg = []
        for i, mkey in enumerate(MKTS_K):
            agg = market_data.get(mkey)
            if agg:
                api_pkg_kg = agg["avg_unit_qty"]  # API 포장 1개당 kg
                price_per_kg = agg["avg_price_per_pkg"] / api_pkg_kg if api_pkg_kg > 0 else 0
                if name == "수박":
                    # 우리 표시는 '1통(9kg)당 원'
                    new_price = max(100, round(price_per_kg * 9))
                else:
                    # 우리 표시는 '박스(BOX_KG)당 원'
                    new_price = max(100, round(price_per_kg * our_box_kg))
                new_vol = round(agg["qty_kg"] / 1000, 1)  # kg -> 톤
                has_agg.append(True)
            else:
                new_price = old_prices[i]
                new_vol = old_vols[i]
                has_agg.append(False)
            # 안전장치 1 (시장 자체 검증): 계산된 가격이 기존가 대비 0.2~5배
            # 범위를 벗어나면 단위 환산 오류로 간주하고 기존가를 유지
            # 단, 백오이는 과거 단위 환산 버그로 old_price 자체가 비정상적으로
            # 작게 누적된 상태이므로, 절대 범위(상자당 5,000~40,000원)로만 검증
            if name == "백오이":
                if not (5000 <= new_price <= 40000):
                    new_price = old_prices[i]
                    has_agg[i] = False
            elif old_prices[i] > 0 and not (old_prices[i] * 0.2 <= new_price <= old_prices[i] * 5):
                new_price = old_prices[i]
                has_agg[i] = False
            new_prices.append(new_price)
            new_vols.append(new_vol)

        # 안전장치 2 (시장간 cross-validation): 이번에 '실데이터로 새로 계산된'
        # (has_agg=True) 시장이 2개 이상일 때만 적용. 그 시장들의 가격 중앙값
        # 대비 2.5배 이상/0.4배 이하로 극단적으로 벗어나는 시장은 단위 환산
        # 오류로 간주해 기존값으로 되돌린다.
        # 실데이터가 1개뿐인 경우(나머지 4개는 placeholder old_price 유지)는
        # 비교 기준이 없으므로 적용하지 않는다 — 그 1개 시장 값을 신뢰한다.
        # (예: 백오이/감귤하우스처럼 한 시장의 소수 특수거래가 가중평균을
        #  왜곡해 다른 실데이터 시장들과 단위가 안 맞아 보이는 케이스만 교정)
        real_indices = [i for i in range(5) if has_agg[i]]
        if len(real_indices) >= 2:
            real_prices = sorted(new_prices[i] for i in real_indices)
            n = len(real_prices)
            mid = n // 2
            median_price = real_prices[mid] if n % 2 else (real_prices[mid - 1] + real_prices[mid]) / 2
            if median_price > 0:
                for i in real_indices:
                    if new_prices[i] > median_price * 2.5 or new_prices[i] < median_price * 0.4:
                        new_prices[i] = old_prices[i]
                        new_vols[i] = old_vols[i]
                        has_agg[i] = False

        new_chgs = []
        for i in range(5):
            chg = round((new_prices[i] - old_prices[i]) / old_prices[i] * 100, 1) if old_prices[i] > 0 else 0.0
            new_chgs.append(chg)
    else:
        # 실데이터 없음 -> 기존 방식(소폭 랜덤 변동)
        base = random.gauss(0, 2.2)
        if random.random() < 0.08:
            base = random.choice([-1, 1]) * random.uniform(7, 15)
        new_prices, new_vols, new_chgs = [], [], []
        for i in range(5):
            chg = max(-18.0, min(22.0, base + random.gauss(0, 0.6)))
            price = max(100, round(old_prices[i] * (1 + chg / 100) / 10) * 10)
            vol = max(0.1, round(old_vols[i] * random.uniform(0.94, 1.06), 1))
            new_prices.append(price)
            new_vols.append(vol)
            new_chgs.append(round(chg, 1))

    p = ",".join(f"{k}:{v}" for k, v in zip(MKTS_K, new_prices))
    c = ",".join(f"{k}:{v}" for k, v in zip(MKTS_K, new_chgs))
    v = ",".join(f"{k}:{v}" for k, v in zip(MKTS_K, new_vols))

    return (
        m.group(1) + p
        + m.group(8) + c
        + m.group(14) + v
        + m.group(20)
    )


count = 0
real_count = 0
def repl(m):
    global count, real_count
    count += 1
    if m.group(2) in results and results[m.group(2)]:
        real_count += 1
    return process(m)

html = ITEM_BLOCK.sub(repl, html)

# ──────────────────────────────────────────
# 3) BOX_KG 동적 갱신 (출하 시기별 SKU 중량 변동 대응)
#    실데이터가 2개 이상 시장에서 확보된 품목의 avg_unit_qty 가중평균으로
#    BOX_KG를 업데이트. 수박은 "통(9kg)" 고정이므로 제외.
# ──────────────────────────────────────────
updated_box_kg = dict(BOX_KG)
for nm, mdata in results.items():
    if nm == "수박":
        continue
    # 실데이터 확보 시장들의 avg_unit_qty를 거래량(qty_kg) 기준 가중평균
    total_kg = sum(agg["qty_kg"] for agg in mdata.values())
    if total_kg <= 0:
        continue
    wavg_unit = sum(agg["avg_unit_qty"] * agg["qty_kg"] for agg in mdata.values()) / total_kg
    # 0.5kg 단위로 반올림 (1.0, 1.5, 2.0, 2.5, 3.0 ... 등 현실적 포장단위)
    rounded = round(wavg_unit * 2) / 2
    if rounded <= 0:
        continue
    old_val = BOX_KG.get(nm, 10)
    # SKU 변동이 명확한 경우에만 갱신 (기존 BOX_KG 대비 0.5배 미만이거나 2배 초과)
    # 소폭 차이(±100% 이내)는 포장 혼재에 의한 자연스러운 가중평균 오차로 보고 유지
    if rounded < old_val * 0.5 or rounded > old_val * 2.0:
        updated_box_kg[nm] = rounded

# BOX_KG 변경사항 디버그 출력
changed = {nm: (BOX_KG.get(nm), v) for nm, v in updated_box_kg.items()
           if BOX_KG.get(nm) != v}
if changed:
    print("--- BOX_KG 갱신 ---")
    for nm, (old, new) in changed.items():
        print(f"  {nm}: {old} -> {new}")

# index.html의 const BOX_KG={...} 재작성
def build_box_kg_str(bk_dict, original_str):
    """원본 문자열의 줄바꿈/정렬 구조를 유지하면서 값만 갱신"""
    def replacer(m):
        key = m.group(1)
        new_val = bk_dict.get(key)
        if new_val is None:
            return m.group(0)
        # 정수면 정수, 소수면 소수 표시
        val_str = str(int(new_val)) if new_val == int(new_val) else str(new_val)
        return f"'{key}':{val_str}"
    return re.sub(r"'([^']+)':([\d.]+)", replacer, original_str)

html = re.sub(
    r"(const BOX_KG=\{)(.*?)(\};)",
    lambda m: m.group(1) + build_box_kg_str(updated_box_kg, m.group(2)) + m.group(3),
    html, flags=re.S
)
BOX_KG = updated_box_kg  # 이후 로직에서 사용될 경우를 위해 업데이트

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

os.makedirs("archive", exist_ok=True)
shutil.copy("index.html", f"archive/{yesterday}.html")

print(f"✅ {now.strftime('%Y-%m-%d %H:%M')} KST — {count}개 품목 처리 (실데이터 반영 {real_count}개)")
if count == 0:
    raise SystemExit("⚠️ 처리된 품목이 0개 — index.html 구조 확인 필요")
