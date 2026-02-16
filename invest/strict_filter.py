import json

def strict_filter():
    with open('/Users/jobiseu/.openclaw/workspace/invest/data/master/coupling_map_raw.json', 'r') as f:
        data = json.load(f)

    semi_keywords = [
        'HBM', 'DDR5', 'TSV', 'OSAT', 'TCB', 'TC-Bonder', 'Hybrid Bonding',
        '패키징', 'packaging', 'DRAM', 'NAND', '반도체', 'semiconductor',
        '하이닉스', '삼성전자', '엔비디아', 'Nvidia', 'TSMC', 'ASML',
        '이오테크닉스', '한미반도체', '피에스케이홀딩스', '테크윙', '제우스',
        '에스티아이', '디아이티', '큐알티', '에스에프에이', '하나마이크론',
        '두산테스나', '엘비세미콘', '네패스', '시그네틱스', 'AP시스템',
        '원익IPS', '유진테크', '주성엔지니어링', '케이씨텍', '넥스틴', '파크시스템스',
        '고영', '인텍플러스', '프롬에이치', '와이씨', '엑시콘', '티에스이', '마이크로컨설팅',
        '리노공업', 'ISC', '티에프이', '동진쌤', '솔브레인', '한양디지텍', '에이디테크놀로지',
        '가온칩스', '오픈엣지', '에이직랜드'
    ]

    filtered = []
    for item in data:
        text = item.get('text', '')
        if any(kw.lower() in text.lower() for kw in semi_keywords):
            filtered.append(item)

    print(f"Total segments: {len(data)}")
    print(f"Strictly Filtered (Semi): {len(filtered)}")

    with open('/Users/jobiseu/.openclaw/workspace/invest/data/master/coupling_map_semi.json', 'w') as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    strict_filter()
