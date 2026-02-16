# RULE_GRADES.md

## MUST (즉시 경고/강제)
- 복구불가 손실/보안/외부영향 위험
- 보고 약속(SLA) 초과
- health-state stale/missing
- pendingMessages 임계치 초과

## SHOULD (다음 heartbeat 1회 권고)
- 품질 저하 가능성이 있는 항목
- 지표/문서 경미한 누락

## CAN (무경고)
- 편의성/정리성 개선 항목
- 즉시 장애와 무관한 선택적 개선

## 운영 원칙
- 경고는 MUST 중심, SHOULD/CAN은 소음 최소화
- 동일 경고는 4시간 이내 재전송 금지
- 야간(22:00~09:00)은 실제 장애만 경고
