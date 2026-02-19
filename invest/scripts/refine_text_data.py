import os
import re
from pathlib import Path

def clean_text(text):
    # Remove boilerplate patterns
    patterns = [
        r"본문 바로가기",
        r"페이지 스크롤 진행률",
        r"Premium Contents",
        r"스타테일 리서치",
        r"검색",
        r"SNS 보내기",
        r"글씨 크기 조정",
        r"by\s+\S+", # e.g. "by 해기사투자자"
        r"\d{4}\.\d{2}\.\d{2}\.\s+오전\s+\d{2}:\d{2}", # e.g. "2026.01.30. 오전 12:55"
        r"\d{4}\.\d{2}\.\d{2}\.\s+오후\s+\d{2}:\d{2}"
    ]
    
    for p in patterns:
        text = re.sub(p, "", text)
    
    # Remove multiple newlines
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()

def run_refinement():
    raw_base = Path("invest/data/raw/text")
    clean_base = Path("invest/data/clean/text")
    
    targets = ["premium/startale", "telegram"]
    
    report = []

    for target in targets:
        src_dir = raw_base / target
        dst_dir = clean_base / target
        dst_dir.mkdir(parents=True, exist_ok=True)
        
        files = list(src_dir.glob("*.md")) + list(src_dir.glob("*.txt"))
        count = 0
        for f in files:
            try:
                content = f.read_text(encoding='utf-8')
                cleaned = clean_text(content)
                
                dst_file = dst_dir / f.name
                dst_file.write_text(cleaned, encoding='utf-8')
                count += 1
            except Exception as e:
                report.append(f"Error refining {f}: {e}")
        
        report.append(f"Refined {count} files in {target}")

    return report

if __name__ == "__main__":
    res = run_refinement()
    for line in res:
        print(line)
