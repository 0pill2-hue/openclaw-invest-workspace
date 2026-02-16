import csv
import json
import os
from datetime import datetime

HEALTH_PATH = "memory/health-state.json"
VALIDATE_PATH = "invest/data/runtime/post_collection_validate.json"
VIX_PATH = "invest/data/macro/VIXCLS.csv"
VIX_WATCH = float(os.environ.get("VIX_WATCH", "30"))
VIX_EXTREME = float(os.environ.get("VIX_EXTREME", "40"))


def _load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _latest_vix_value():
    if not os.path.exists(VIX_PATH):
        return None
    latest = None
    with open(VIX_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            v = row.get("VIXCLS")
            if not v or v == ".":
                continue
            try:
                latest = float(v)
            except Exception:
                continue
    return latest


def build_alerts():
    alerts = []
    health = _load_json(HEALTH_PATH) or {}
    validate = _load_json(VALIDATE_PATH) or {}

    cf = int(health.get("consecutiveFailures", 0) or 0)
    pm = int(health.get("pendingMessages", 0) or 0)
    if cf >= 2:
        alerts.append(f"운영 경보: 자동복구 연속 실패 {cf}회입니다. 수집 안정성이 흔들려 즉시 점검이 필요합니다.")
    if pm > 10:
        alerts.append(f"운영 경보: 메시지 큐 적체 {pm}건입니다. 알림 지연 가능성이 있습니다.")

    failed = int(validate.get("failed_count", 0) or 0)
    if failed > 0:
        first = (validate.get("failures") or [{}])[0]
        script = first.get("script", "unknown")
        alerts.append(
            f"데이터 경보: 수집 검증 실패 {failed}건(첫 항목: {script}). 이 상태에선 알고리즘 입력 품질 저하 위험이 있습니다."
        )

    vix = _latest_vix_value()
    if vix is not None:
        if vix >= VIX_EXTREME:
            alerts.append(
                f"시장 경보: VIX {vix:.2f} (극단 공포 구간). 설명: 단기 변동성은 매우 높지만, 역사적으로 분할매수 기회가 자주 나온 구간입니다."
            )
        elif vix >= VIX_WATCH:
            alerts.append(
                f"시장 경보: VIX {vix:.2f} (공포 확대 구간). 설명: 추격매도보다 관찰/분할진입 준비가 유리한 매수기회 후보 구간입니다."
            )

    return alerts


def main():
    alerts = build_alerts()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if alerts:
        print(f"ALERT_TRIGGER|{now}|count={len(alerts)}")
        for a in alerts:
            print(f"- {a}")
    else:
        print("ALERT_TRIGGER|OK")


if __name__ == "__main__":
    main()
