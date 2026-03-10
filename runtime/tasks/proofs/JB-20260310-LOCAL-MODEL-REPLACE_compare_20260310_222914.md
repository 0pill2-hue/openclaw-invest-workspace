# JB-20260310-LOCAL-MODEL-REPLACE 비교 리포트 (20260310_222914)

## 테스트 조건
- Prompt: `아래 지표만 보고 투자 메모 초안을 작성하라. 반드시 한국어 JSON만 출력하고 키는 conclusion, positives, risks, verdict를 사용하라. positives와 risks는 각각 3개 배열이어야 한다. 지표: 매출 +20%, 영업이익 -5%, 잉여현금흐름 -12%, 부채비율 +10%p, 신규계약 2건, 재고회전일수 악화.`
- Server args: `llama-server -m <MODEL> --host 127.0.0.1 --port 8090 -c 12288 -ngl 99 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.5 --top-p 0.9 --top-k 20 --min-p 0.02 --repeat-penalty 1.05 --repeat-last-n 128 --chat-template-kwargs {"enable_thinking": false}`
- 각 모델당 동일 프롬프트 3회, temperature=0.0, max_tokens=220

## Qwen3.5-35B-A3B-Q4_K_M
- ready_sec: 4.788
- avg/min/max latency_sec: 11.084 / 11.044 / 11.109
- stderr_log: `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/JB-20260310-LOCAL-MODEL-REPLACE_Qwen3.5-35B-A3B-Q4_K_M_20260310_222914.stderr.log`

### run 1
- ok: True
- latency_sec: 11.044
- usage: {"prompt_tokens": 100, "completion_tokens": 220, "total_tokens": 320}
- text:
```json
{
  "conclusion": "매출 성장은 지속되나 비용 증가와 현금 흐름 악화로 수익성 및 재무 건전성이 동시에 훼손되고 있어 주의가 필요함.",
  "positives": [
    "매출이 전년 대비 20% 성장하며 시장 점유율 확대 또는 수요 증가를 시사",
    "신규 계약 2건 체결로 향후 매출 기반이 확보됨",
    "매출 규모 확대로 인한 시장 내 입지 강화 가능성"
  ],
  "risks": [
    "영업이익이 5% 감소하여 매출 증가분이 비용 증가에 흡수된 비효율적 운영 구조",
    "잉여현금흐름이 12% 감소하여 유동성 위험 및 투자 여력 축소",
    "부채비율이 10%p 상승하고 재고회전일수가 악화되어 재무 리스크와 재고 부담 동시 발생"
  ],
  "verdict": "단기적인 성장세는 있으나 수익성과 현금 창출 능
```

### run 2
- ok: True
- latency_sec: 11.109
- usage: {"prompt_tokens": 100, "completion_tokens": 220, "total_tokens": 320}
- text:
```json
{
  "conclusion": "매출 성장은 지속되나 비용 증가와 현금 흐름 악화로 수익성 및 재무 건전성이 동시에 훼손되고 있어 주의가 필요함.",
  "positives": [
    "매출이 전년 대비 20% 성장하며 시장 점유율 확대 또는 수요 증가를 시사",
    "신규 계약 2건 체결로 향후 매출 기반이 확보됨",
    "매출 규모 확대로 인한 시장 내 입지 강화 가능성"
  ],
  "risks": [
    "영업이익이 5% 감소하여 매출 증가분이 비용 증가에 흡수된 비효율적 운영 구조",
    "잉여현금흐름이 12% 감소하여 유동성 위험 및 투자 여력 축소",
    "부채비율이 10%p 상승하고 재고회전일수가 악화되어 재무 리스크와 재고 부담 동시 발생"
  ],
  "verdict": "단기적인 성장세는 있으나 수익성과 현금 창출 능
```

### run 3
- ok: True
- latency_sec: 11.098
- usage: {"prompt_tokens": 100, "completion_tokens": 220, "total_tokens": 320}
- text:
```json
{
  "conclusion": "매출 성장은 지속되나 비용 증가와 현금 흐름 악화로 수익성 및 재무 건전성이 동시에 훼손되고 있어 주의가 필요함.",
  "positives": [
    "매출이 전년 대비 20% 성장하며 시장 점유율 확대 또는 수요 증가를 시사",
    "신규 계약 2건 체결로 향후 매출 기반이 확보됨",
    "매출 규모 확대로 인한 시장 내 입지 강화 가능성"
  ],
  "risks": [
    "영업이익이 5% 감소하여 매출 증가분이 비용 증가에 흡수된 비효율적 운영 구조",
    "잉여현금흐름이 12% 감소하여 유동성 위험 및 투자 여력 축소",
    "부채비율이 10%p 상승하고 재고회전일수가 악화되어 재무 리스크와 재고 부담 동시 발생"
  ],
  "verdict": "단기적인 성장세는 있으나 수익성과 현금 창출 능
```

## Qwen3.5-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled.i1-Q4_K_M
- ready_sec: 25.419
- avg/min/max latency_sec: 11.151 / 10.98 / 11.475
- stderr_log: `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/JB-20260310-LOCAL-MODEL-REPLACE_Qwen3.5-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled.i1-Q4_K_M_20260310_222914.stderr.log`

### run 1
- ok: True
- latency_sec: 10.999
- usage: {"prompt_tokens": 99, "completion_tokens": 220, "total_tokens": 319}
- text:
```json


```json
{
  "conclusion": "매출 성장세는 유지되나 수익성 악화와 재무 건전성 저하로 인해 단기적인 투자 리스크가 높음",
  "positives": [
    "매출이 전년 대비 20% 증가하며 시장 점유율 확대 가능성 확인",
    "신규 계약 2건 체결로 향후 매출 기반 마련",
    "매출 성장률 양호한 수준 유지"
  ],
  "risks": [
    "영업이익 마진 축소 (-5%) 로 수익성 악화 우려",
    "잉여현금흐름 감소 (-12%) 로 자금 조달 능력 약화",
    "부채비율 상승 (+10%p) 및 재고회전일수 악화로 재무 리스크 증가"
  ],
  "verdict": "단기적 관점에서는 매도 또는观望 권고, 장기적 관점에서는 구조조정 및 비용 절감 효과 확인 후 재평가 필요"
}
```
```

### run 2
- ok: True
- latency_sec: 11.475
- usage: {"prompt_tokens": 99, "completion_tokens": 220, "total_tokens": 319}
- text:
```json


```json
{
  "conclusion": "매출 성장세는 유지되나 수익성 악화와 재무 건전성 저하로 인해 단기적인 투자 리스크가 높음",
  "positives": [
    "매출이 전년 대비 20% 증가하며 시장 점유율 확대 가능성 확인",
    "신규 계약 2건 체결로 향후 매출 기반 마련",
    "매출 성장률 양호한 수준 유지"
  ],
  "risks": [
    "영업이익 마진 축소 (-5%) 로 수익성 악화 우려",
    "잉여현금흐름 감소 (-12%) 로 자금 조달 능력 약화",
    "부채비율 상승 (+10%p) 및 재고회전일수 악화로 재무 리스크 증가"
  ],
  "verdict": "단기적 관점에서는 매도 또는观望 권고, 장기적 관점에서는 구조조정 및 비용 절감 효과 확인 후 재평가 필요"
}
```
```

### run 3
- ok: True
- latency_sec: 10.98
- usage: {"prompt_tokens": 99, "completion_tokens": 220, "total_tokens": 319}
- text:
```json


{
  "conclusion": "매출 성장세는 유지되나 수익성 악화와 재무 건전성 저하가 동시에 발생하여 단기적인 투자 리스크가 높음.",
  "positives": [
    "매출이 전년 대비 20% 증가하며 시장에서의 수요 확보 및 성장 가능성이 확인됨",
    "신규 계약 2건 체결로 향후 매출 기반이 확대될 잠재력이 있음",
    "매출 규모 확장을 통해 시장 점유율 제고 가능성 존재"
  ],
  "risks": [
    "영업이익이 5% 감소하여 매출 증가분이 비용 증가에 흡수되거나 원가 경쟁력 약화 우려",
    "잉여현금흐름이 12% 감소하여 자금 조달 능력과 배당 여력이 축소됨",
    "부채비율이 10%p 상승하고 재고회전일수가 악화되어 유동성 위험 및 운영 효율성 저하"
  ],
  "verdict": "단기적으로는
```

## Restore
{
  "ok": true,
  "ready_sec": 4.878,
  "error": null
}