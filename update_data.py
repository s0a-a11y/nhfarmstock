import os
import shutil
from datetime import datetime, timedelta

# 날짜 설정
today = datetime.now().strftime('%Y-%m-%d')
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

# index.html 읽기
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 날짜 텍스트 업데이트
from datetime import datetime
now = datetime.now()
weekdays = ['월','화','수','목','금','토','일']
day_str = f"{now.year}. {now.month:02d}. {now.day:02d} ({weekdays[now.weekday()]})"

# 기존 날짜 패턴 교체
import re
html = re.sub(
    r'\d{4}\. \d{2}\. \d{2} \([월화수목금토일]\)',
    day_str,
    html
)

# 업데이트된 index.html 저장
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

# archive 폴더에 어제 날짜로 보관
os.makedirs('archive', exist_ok=True)
shutil.copy('index.html', f'archive/{yesterday}.html')

print(f"✅ {today} 업데이트 완료")
