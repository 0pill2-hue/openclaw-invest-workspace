import os
import pandas as pd
import json
import glob
from datetime import datetime

def get_csv_range(pattern):
    files = glob.glob(pattern)
    if not files:
        return 0, None, None
    
    min_dates = []
    max_dates = []
    
    # Sample some files if there are too many
    if len(files) > 100:
        files = files[:100]
        
    for f in files:
        try:
            df = pd.read_csv(f)
            # Find date column
            date_col = None
            for col in ['Date', 'date', '날짜', 'published']:
                if col in df.columns:
                    date_col = col
                    break
            
            if date_col:
                dates = pd.to_datetime(df[date_col], errors='coerce').dropna()
                if not dates.empty:
                    min_dates.append(dates.min())
                    max_dates.append(dates.max())
        except:
            continue
            
    if not min_dates:
        return len(files), None, None
    
    return len(files), min(min_dates), max(max_dates)

def get_md_range(directory):
    files = glob.glob(os.path.join(directory, "**/*.md"), recursive=True)
    if not files:
        return 0, None, None
    
    dates = []
    # Sample some files
    sample_files = files[:200]
    for f in sample_files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                content = file.read()
                # Try to find Date: YYYY. MM. DD. or similar
                import re
                m = re.search(r'Date:\s*(20\d{2})\s*[\.\-/]\s*(\d{1,2})\s*[\.\-/]\s*(\d{1,2})', content)
                if m:
                    dates.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))))
                else:
                    # Try file mtime as fallback
                    dates.append(datetime.fromtimestamp(os.path.getmtime(f)))
        except:
            continue
            
    if not dates:
        return len(files), None, None
        
    return len(files), min(dates), max(dates)

def get_json_range(directory):
    files = glob.glob(os.path.join(directory, "*.json"))
    if not files:
        return 0, None, None
    
    dates = []
    for f in files:
        try:
            # For RSS, the filename has the date rss_YYYYMMDD-HHMMSS.json
            import re
            m = re.search(r'rss_(\d{8})', f)
            if m:
                dates.append(datetime.strptime(m.group(1), '%Y%m%d'))
            else:
                dates.append(datetime.fromtimestamp(os.path.getmtime(f)))
        except:
            continue
            
    if not dates:
        return len(files), None, None
        
    return len(files), min(dates), max(dates)

sources = {
    "kr/ohlcv": ("invest/data/raw/kr/ohlcv/*.csv", "csv"),
    "kr/supply": ("invest/data/raw/kr/supply/*.csv", "csv"),
    "us/ohlcv": ("invest/data/raw/us/ohlcv/*.csv", "csv"),
    "kr/dart": ("invest/data/raw/kr/dart/*.csv", "csv"),
    "market/news/rss": ("invest/data/raw/market/news/rss", "json_dir"),
    "market/macro": ("invest/data/raw/market/macro/*.csv", "csv"),
    "market/google_trends": ("invest/data/raw/market/google_trends/*.csv", "csv"),
    "text/blog": ("invest/data/raw/text/blog", "md_dir"),
    "text/telegram": ("invest/data/raw/text/telegram", "md_dir"),
    "text/premium": ("invest/data/raw/text/premium", "md_dir"),
    "text/image_map": ("invest/data/raw/text/image_map/*.json", "count_only"),
    "text/images_ocr": ("invest/data/raw/text/images_ocr/*.json", "count_only"),
}

results = []
for name, (path, type) in sources.items():
    print(f"Checking {name}...")
    if type == "csv":
        count, start, end = get_csv_range(path)
    elif type == "md_dir":
        count, start, end = get_md_range(path)
    elif type == "json_dir":
        count, start, end = get_json_range(path)
    elif type == "count_only":
        files = glob.glob(path)
        count, start, end = len(files), None, None
    
    results.append({
        "Source": name,
        "File Count": count,
        "Min Date": start.strftime('%Y-%m-%d') if start else "N/A",
        "Max Date": end.strftime('%Y-%m-%d') if end else "N/A",
    })

df = pd.DataFrame(results)
print(df.to_string(index=False))
df.to_csv("coverage_baseline.csv", index=False)
