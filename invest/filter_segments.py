import json
import re

def analyze_relationships():
    with open('/Users/jobiseu/.openclaw/workspace/invest/data/master/coupling_map_raw.json', 'r') as f:
        data = json.load(f)

    keywords = [
        '공급', '납품', '수주', '파트너', '협력', '고객사', '체결', '유통', '양산',
        'supply', 'deliver', 'provide', 'partner', 'contract', 'customer', 'client',
        'HBM', 'DDR5', 'TSV', 'OSAT', 'TCB', 'TC-Bonder', 'Hybrid Bonding',
        '패키징', 'packaging', '장비', '소재', '부품', '하이닉스', '삼성', '엔비디아', 'TSMC', '인텔'
    ]

    filtered = []
    for item in data:
        text = item.get('text', '')
        if any(kw.lower() in text.lower() for kw in keywords):
            filtered.append(item)

    print(f"Total segments: {len(data)}")
    print(f"Filtered segments: {len(filtered)}")

    # Save filtered for inspection or further processing
    with open('/Users/jobiseu/.openclaw/workspace/invest/data/master/coupling_map_filtered.json', 'w') as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    analyze_relationships()
