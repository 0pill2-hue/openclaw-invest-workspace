# openclaw-invest-workspace

투자 데이터 수집/정제/검증/백테스트를 위한 OpenClaw 워크스페이스입니다.

## 핵심 목표

- 데이터 오염 방지 (raw / clean / quarantine 분리)
- 재현 가능한 단계별 실행 (stage별 inputs/outputs/scripts/docs 고정)
- 운영 안정화 (실패 시 fail-close + 증적 리포트)

## 디렉토리 개요

- `invest/docs/` : 공통 정책/운영 문서
- `invest/stages/stageN/{inputs,outputs,scripts,docs}` : stage별 canonical 구조

## 빠른 시작 (신규 번호 체계)

```bash
# 1) Stage1 수집
python3 invest/stages/stage1/scripts/stage01_daily_update.py

# 2) Stage2 정제/QC (ohlcv/supply + dart/news/text)
python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py

# 3) Stage3 로컬뇌 입력 생성 + 정성 게이트
python3 invest/stages/stage3/scripts/stage03_build_input_jsonl.py
python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py --bootstrap-empty-ok

# 4) Stage4 값 계산
python3 invest/stages/stage4/scripts/calculate_stage4_values.py

# 5) Stage5 피처 엔지니어링
python3 invest/stages/stage5/scripts/stage05_feature_engineer.py

# 6) Stage6 베이스라인 재계산/검증
python3 invest/stages/stage6/scripts/stage06_full_recompute_v4_6_kr.py
```

## 운영 규칙(요약)

- upstream 입력은 각 stage의 `inputs/upstream_*` 경유
- 결과 라벨: `DRAFT | VALIDATED | PRODUCTION`
- 검증 실패 시 downstream 차단(fail-close)

## 관련 문서

- `invest/docs/INVEST_STRUCTURE_POLICY.md`
- `invest/docs/BOOTSTRAP_REPRODUCTION.md`
- `invest/docs/STAGE_EXECUTION_SPEC.md`
- `invest/docs/STRATEGY_MASTER.md`
