import os
import glob
import random
import re
from datetime import datetime

def get_sample_files(base_paths, sample_ratio=0.1):
    all_files = []
    for base_path in base_paths:
        files = glob.glob(os.path.join(base_path, '**', '*.md'), recursive=True)
        all_files.extend(files)
    
    sample_size = max(1, int(len(all_files) * sample_ratio))
    return random.sample(all_files, sample_size)

def check_file_qc(file_path):
    """
    파일 단위 QC
    - 0바이트: 0byte
    - 읽기 불가: UnicodeDecodeError 등
    - 메타/본문 모두 부재: 파싱 결과 둘다 없음
    """
    try:
        if os.path.getsize(file_path) == 0:
            return "quarantine", "0-byte file"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if not content.strip():
            return "quarantine", "Empty content"
            
        return "clean", content
    except Exception as e:
        return "quarantine", f"Read error: {str(e)}"

def check_line_qc(line, source_type):
    """
    행/문단 단위 QC
    - 날짜 파싱 실패 메타라인 (Blog: Date: 로 시작하는데 날짜 형식 아님)
    - 완전 공백
    - 제어문자 과다 (비율 10% 이상 혹은 연속 3개 이상 등 - 간단히 패턴 체크)
    """
    stripped = line.strip()
    if not stripped:
        return "quarantine", "Empty line"
    
    # 제어문자/특수문자 과다 (단순 구현: 비ASCII 문자 중 한글/일반문장부호 제외 비율이 높을 때)
    # 여기서는 간단하게 제어문자 (\x00-\x1f) 존재 여부로 체크
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', line):
        return "quarantine", "Control characters detected"

    if source_type == 'blog':
        if stripped.startswith('Date:'):
            # Date: 2021. 5. 8. 형식 체크
            date_val = stripped.replace('Date:', '').strip()
            if not re.match(r'^\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?$', date_val):
                return "quarantine", "Invalid Date meta format"
    
    elif source_type == 'telegram':
        if stripped.startswith('Date:'):
            # Date: 2026-02-12 12:20:21 형식 체크
            date_val = stripped.replace('Date:', '').strip()
            if not re.match(r'^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}$', date_val):
                return "quarantine", "Invalid Date meta format"

    return "clean", None

def run_qc():
    base_paths = [
        'invest/data/raw/text/blog',
        'invest/data/raw/text/telegram'
    ]
    
    sample_files = get_sample_files(base_paths)
    
    report = {
        "total_files": len(sample_files),
        "clean_files": 0,
        "quarantine_files": 0,
        "total_lines": 0,
        "clean_lines": 0,
        "quarantine_lines": 0,
        "quarantine_list": [], # (file_path, reason)
        "folder_stats": {} # folder -> clean_count
    }
    
    for file_path in sample_files:
        rel_dir = os.path.dirname(os.path.relpath(file_path, 'invest/data/raw/text'))
        if rel_dir not in report["folder_stats"]:
            report["folder_stats"][rel_dir] = 0
            
        source_type = 'blog' if 'blog' in file_path else 'telegram'
        
        status, content_or_reason = check_file_qc(file_path)
        
        if status == "quarantine":
            report["quarantine_files"] += 1
            report["quarantine_list"].append((file_path, content_or_reason))
            continue
            
        # Line by line QC
        lines = content_or_reason.splitlines()
        file_clean_lines = 0
        file_quarantine_lines = 0
        
        for line in lines:
            report["total_lines"] += 1
            l_status, l_reason = check_line_qc(line, source_type)
            if l_status == "clean":
                file_clean_lines += 1
                report["clean_lines"] += 1
            else:
                file_quarantine_lines += 1
                report["quarantine_lines"] += 1
        
        if file_clean_lines > 0:
            report["clean_files"] += 1
            report["folder_stats"][rel_dir] += 1
        else:
            report["quarantine_files"] += 1
            report["quarantine_list"].append((file_path, "All lines quarantined"))

    # Final Report Generation
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = f'reports/qc/QC_TEXT_REPORT_{timestamp}.md'
    os.makedirs('reports/qc', exist_ok=True)
    
    clean_ratio = (report["clean_files"] / report["total_files"] * 100) if report["total_files"] > 0 else 0
    line_clean_ratio = (report["clean_lines"] / report["total_lines"] * 100) if report["total_lines"] > 0 else 0
    zero_clean_folders = [f for f, count in report["folder_stats"].items() if count == 0]
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# QC Text Report ({timestamp})\n\n")
        f.write(f"## Summary\n")
        f.write(f"- Total Sample Files: {report['total_files']}\n")
        f.write(f"- Clean Files: {report['clean_files']}\n")
        f.write(f"- Quarantine Files: {report['quarantine_files']}\n")
        f.write(f"- Clean Ratio (File): {clean_ratio:.2f}%\n")
        f.write(f"- Total Lines: {report['total_lines']}\n")
        f.write(f"- Clean Lines: {report['clean_lines']}\n")
        f.write(f"- Quarantine Lines: {report['quarantine_lines']}\n")
        f.write(f"- Clean Ratio (Line): {line_clean_ratio:.2f}%\n\n")
        
        f.write(f"## Folder Issues\n")
        if zero_clean_folders:
            f.write(f"- Folders with 0 clean files: {', '.join(zero_clean_folders[:10])}...\n")
        else:
            f.write(f"- All folders have at least one clean file.\n")
            
        f.write(f"\n## Top 20 Quarantined Files\n")
        for fp, reason in report["quarantine_list"][:20]:
            f.write(f"- `{fp}`: {reason}\n")

    print(f"Report generated: {report_path}")
    print(f"Summary: Files={report['total_files']}, Clean={report['clean_files']}, Q={report['quarantine_files']}, Ratio={clean_ratio:.2f}%")
    if zero_clean_folders:
        print(f"Folders with 0 clean: {len(zero_clean_folders)}")

if __name__ == "__main__":
    run_qc()
