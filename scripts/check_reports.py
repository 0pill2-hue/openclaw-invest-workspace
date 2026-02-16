import os
import re
from datetime import datetime, timedelta

TASKS_FILE = "/Users/jobiseu/.openclaw/workspace/TASKS.md"

def check_reports():
    if not os.path.exists(TASKS_FILE):
        return

    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    now = datetime.now()
    pending_reports = []
    
    # 정규식: [ ] [PENDING] YYYY-MM-DD HH:MM | task | @target | Pn
    pattern = r"- \[ \] \[PENDING\] (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| (.*?) \| @(\w+) \| P(\d)"

    for line in lines:
        match = re.search(pattern, line)
        if match:
            due_str, task, target, priority = match.groups()
            due_time = datetime.strptime(due_str, "%Y-%m-%d %H:%M")
            
            # 마감 임박 (10분 전) 또는 경과
            if now >= due_time - timedelta(minutes=10):
                status = "🚨 지연" if now > due_time else "⏰ 임박"
                pending_reports.append(f"{status} (P{priority}) {task} [대상: {target}, 마감: {due_str}]")

    if pending_reports:
        print("\n".join(pending_reports))
    else:
        print("OK: No urgent reports.")

if __name__ == "__main__":
    # 실제 구현 시에는 datetime 파싱 오류 처리를 위해 더 정교한 포맷팅 필요
    try:
        check_reports()
    except Exception as e:
        print(f"Error: {e}")
