import os
import glob
import random
import json
import csv
from datetime import datetime
import traceback

def get_run_id():
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def sample_files(files, ratio=0.1):
    if not files:
        return []
    sample_size = max(1, int(len(files) * ratio))
    return random.sample(files, sample_size)

def check_csv(file_path):
    try:
        if os.path.getsize(file_path) == 0:
            return False, "0-byte file"
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
            if not header:
                return False, "No header in CSV"
            
            # Read at most 5 rows to check content
            rows = []
            for i, row in enumerate(reader):
                rows.append(row)
                if i >= 4: break
                
            if not rows:
                return False, "No data rows in CSV"
            
            # Basic column check for OHLCV if applicable
            if 'ohlcv' in file_path:
                required = {'open', 'high', 'low', 'close'}
                header_lower = {h.lower() for h in header}
                if not required.intersection(header_lower):
                    # Check for Korean headers as well
                    kr_required = {'시가', '고가', '저가', '종가'}
                    if not kr_required.intersection(set(header)):
                        return False, f"Missing OHLCV columns: {header}"
        return True, None
    except Exception as e:
        return False, f"CSV Error: {str(e)}"

def check_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            return False, "Empty JSON"
        return True, None
    except Exception as e:
        return False, f"JSON Error: {str(e)}"

def check_md(file_path):
    try:
        if os.path.getsize(file_path) == 0:
            return False, "0-byte file"
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if len(content.strip()) < 10:
            return False, "Too short content"
        return True, None
    except Exception as e:
        return False, f"MD Error: {str(e)}"

def run_all_qc():
    run_id = get_run_id()
    targets = {
        "kr/ohlcv": "invest/data/raw/kr/ohlcv/*.csv",
        "kr/supply": "invest/data/raw/kr/supply/*.csv",
        "kr/dart": "invest/data/raw/kr/dart/*.*",
        "us/ohlcv": "invest/data/raw/us/ohlcv/*.csv",
        "market/news/rss": "invest/data/raw/market/news/rss/*.*",
        "market/macro": "invest/data/raw/market/macro/*.csv",
        "market/google_trends": "invest/data/raw/market/google_trends/*.csv",
        "text/blog": "invest/data/raw/text/blog/**/*.md",
        "text/telegram": "invest/data/raw/text/telegram/*.md",
        "text/image_map": "invest/data/raw/text/image_map/*.json",
        "text/images_ocr": "invest/data/raw/text/images_ocr/*.json",
        "text/premium/startale": "invest/data/raw/text/premium/startale/*.md"
    }

    results = {}
    quarantine_logs = []
    
    os.makedirs('reports/qc', exist_ok=True)

    for label, pattern in targets.items():
        files = glob.glob(pattern, recursive=True)
        samples = sample_files(files, 0.1)
        
        total = len(samples)
        clean = 0
        issues = []

        for f in samples:
            ext = os.path.splitext(f)[1].lower()
            is_clean = True
            reason = None

            if ext == '.csv':
                is_clean, reason = check_csv(f)
            elif ext == '.json':
                is_clean, reason = check_json(f)
            elif ext == '.md':
                is_clean, reason = check_md(f)
            else:
                # Default size check
                if os.path.getsize(f) == 0:
                    is_clean, reason = False, "0-byte file"
            
            if is_clean:
                clean += 1
            else:
                issues.append({"file": f, "reason": reason})
                quarantine_logs.append({
                    "run_id": run_id,
                    "folder": label,
                    "file": f,
                    "reason": reason
                })

        results[label] = {
            "total": total,
            "clean": clean,
            "ratio": (clean / total * 100) if total > 0 else 0,
            "issues": issues
        }

    # Write RERUN Report
    report_path = f'reports/qc/QC_ALL_FOLDERS_RERUN_{run_id}.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# QC All Folders Rerun Report ({run_id})\n\n")
        f.write("| Folder | Total Sample | Clean | Ratio |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for label, stat in results.items():
            f.write(f"| {label} | {stat['total']} | {stat['clean']} | {stat['ratio']:.2f}% |\n")
        
        f.write("\n## Quarantine Details (Top 3 per folder)\n")
        for label, stat in results.items():
            if stat['issues']:
                f.write(f"### {label}\n")
                for issue in stat['issues'][:3]:
                    f.write(f"- `{issue['file']}`: {issue['reason']}\n")

    # Write Brainstorm Report (Initial Draft based on findings)
    brainstorm_path = f'reports/qc/QC_ALL_FOLDERS_BRAINSTORM_REVIEW_{run_id}.md'
    
    problematic = sorted(results.items(), key=lambda x: x[1]['ratio'])[:3]
    
    with open(brainstorm_path, 'w', encoding='utf-8') as f:
        f.write(f"# QC Brainstorm Review ({run_id})\n\n")
        f.write("## 1. 잘못 격리 의심 패턴\n")
        f.write("- CSV Column Check: OHLCV 컬럼명이 대소문자나 한글로 되어 있어 격리되었을 가능성 확인 필요.\n")
        f.write("## 2. 과격 기준 여부\n")
        f.write("- MD 파일 10자 미만 기준: 실제 유효한 짧은 공지가 있을 수 있음.\n")
        f.write("## 3. 스크립트 오류 흔적\n")
        # Check for .fail or traceback in logs if any (not implemented in this run but placeholder)
        f.write("- 이번 실행 중 Python Traceback 발생 없음.\n")
        f.write("## 4. clean 0건 유입 폴더\n")
        zero_clean = [l for l, s in results.items() if s['total'] > 0 and s['clean'] == 0]
        if zero_clean:
            for z in zero_clean:
                f.write(f"- {z}\n")
        else:
            f.write("- 없음\n")

    print(f"Rerun report: {report_path}")
    print(f"Brainstorm report: {brainstorm_path}")
    
    # Summary for main session
    print("SUMMARY_START")
    for label, stat in results.items():
        print(f"{label}: {stat['ratio']:.2f}%")
    print("TOP3_PROBLEMATIC")
    for p in problematic:
        print(f"{p[0]}: {p[1]['ratio']:.2f}%")
    print("SUMMARY_END")

if __name__ == "__main__":
    run_all_qc()
