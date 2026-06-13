# -*- coding: utf-8 -*-
"""
NH_Farm_Stock 일일 시황 리포트 자동 발송
- index.html 데이터를 파싱해 시황 요약 생성
- 이메일(Gmail) + 카카오톡(나에게 보내기) 발송
- GitHub Actions에서 매일 08:00 KST 실행
"""
import os, re, ssl, smtplib, datetime, json
from email.mime.text import MIMEText
from email.header import Header

try:
    import requests
except ImportError:
    requests = None

SITE_URL = "https://nhfarmstock.com"

# ──────────────────────────────────────────
# 1. index.html 데이터 파싱
# ──────────────────────────────────────────
HTML = open("index.html", encoding="utf-8").read()

box_m = re.search(r"const BOX_KG=\{(.*?)\};", HTML, re.S)
BOX = dict(re.findall(r"'([^']+)':(\d+)", box_m.group(1))) if box_m else {}

piece_m = re.search(r"const PIECE_ITEMS=\{(.*?)\};", HTML, re.S)
PIECE = dict(re.findall(r"'([^']+)':(\d+)", piece_m.group(1))) if piece_m else {}

items = []
pat = re.compile(
    r"\{name:'([^']+)',en:'[^']*'.*?"
    r"prices:\{garak:(\d+).*?"
    r"chg:\{garak:([-\d.]+),daejeon:([-\d.]+),busan:([-\d.]+),gwangju:([-\d.]+),daegu:([-\d.]+)\}.*?"
    r"insight:'([^']*)'",
    re.S,
)
for m in pat.finditer(HTML):
    name = m.group(1)
    garak_box = int(m.group(2))
    chgs = [float(m.group(i)) for i in range(3, 8)]
    div = int(PIECE.get(name) or BOX.get(name, 10))
    unit = "개" if name in PIECE else "kg"
    items.append({
        "name": name,
        "price": round(garak_box / div),
        "unit": unit,
        "chg": round(sum(chgs) / 5, 1),
        "insight": m.group(7),
    })

if not items:
    raise SystemExit("index.html 파싱 실패 — 데이터 구조를 확인하세요.")

# ──────────────────────────────────────────
# 2. 시황 요약 작성
# ──────────────────────────────────────────
today = datetime.datetime.utcnow() + datetime.timedelta(hours=9)  # KST
date_str = today.strftime("%Y.%m.%d (%a)")

up = sorted(items, key=lambda x: -x["chg"])[:3]
dn = sorted(items, key=lambda x: x["chg"])[:3]
up_cnt = sum(1 for i in items if i["chg"] >= 0)

def line(i):
    arrow = "▲" if i["chg"] >= 0 else "▼"
    return f"  {i['name']} {i['price']:,}원/{i['unit']} {arrow}{abs(i['chg'])}%"

summary = f"""🌾 NH_Farm_Stock 일일 시황 — {date_str}

📈 급등 TOP 3 (가락 특품 기준)
{chr(10).join(line(i) for i in up)}

📉 급락 TOP 3
{chr(10).join(line(i) for i in dn)}

📊 전체 {len(items)}개 품목 중 상승 {up_cnt}개 / 하락 {len(items)-up_cnt}개

💡 오늘의 포인트
  · {up[0]['name']}: {up[0]['insight']}
  · {dn[0]['name']}: {dn[0]['insight']}

🔗 실시간 상세: {SITE_URL}
"""
print(summary)

# ──────────────────────────────────────────
# 3. 이메일 발송 (Gmail)
# ──────────────────────────────────────────
MAIL_USER = os.environ.get("MAIL_USERNAME", "")
MAIL_PASS = os.environ.get("MAIL_PASSWORD", "")
MAIL_TO = os.environ.get("MAIL_TO", "")

if MAIL_USER and MAIL_PASS and MAIL_TO:
    msg = MIMEText(summary, "plain", "utf-8")
    msg["Subject"] = Header(f"[NH_Farm_Stock] {date_str} 농산물 시황 요약", "utf-8")
    msg["From"] = MAIL_USER
    msg["To"] = MAIL_TO
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(MAIL_USER, MAIL_PASS)
        s.sendmail(MAIL_USER, [a.strip() for a in MAIL_TO.split(",")], msg.as_string())
    print("✅ 이메일 발송 완료")
else:
    print("⏭️ 이메일 시크릿 미설정 — 건너뜀")

# ──────────────────────────────────────────
# 4. 카카오톡 나에게 보내기
# ──────────────────────────────────────────
KAKAO_KEY = os.environ.get("KAKAO_REST_KEY", "")
KAKAO_REFRESH = os.environ.get("KAKAO_REFRESH_TOKEN", "")
KAKAO_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "")

if KAKAO_KEY and KAKAO_REFRESH and requests:
    payload = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_KEY,
        "refresh_token": KAKAO_REFRESH,
    }
    if KAKAO_SECRET:
        payload["client_secret"] = KAKAO_SECRET
    tok = requests.post("https://kauth.kakao.com/oauth/token", data=payload).json()
    access = tok.get("access_token")
    if not access:
        print("❌ 카카오 토큰 갱신 실패:", tok)
    else:
        # 카톡은 글자수 제한이 있어 핵심만 발송
        kakao_text = summary[:950]
        r = requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={"Authorization": f"Bearer {access}"},
            data={"template_object": json.dumps({
                "object_type": "text",
                "text": kakao_text,
                "link": {"web_url": SITE_URL, "mobile_web_url": SITE_URL},
                "button_title": "실시간 시세 보기",
            }, ensure_ascii=False)},
        )
        print("✅ 카카오톡 발송 완료" if r.status_code == 200 else f"❌ 카카오 발송 실패: {r.text}")
else:
    print("⏭️ 카카오 시크릿 미설정 — 건너뜀")
