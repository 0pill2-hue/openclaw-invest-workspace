# BOOTSTRAP_REPRODUCTION

## L0) 요약

- 본 문서는 Stage1~6 재현용 최소 부트스트랩이다.
- 실행 순서는 **Stage1 → Stage2 → Stage3 → Stage4 → Stage5 → Stage6** 고정이다.
- 각 Stage는 자신의 `inputs/` 경유 입력만 사용하고 `outputs/`에만 기록한다.
- Stage1 raw는 `signal` vs `qualitative`로 분리한다.
  - `raw/signal/*`: 수치/시계열(직접 스코어링 입력 가능)
  - `raw/qualitative/*`: 비정형(중간 추출/파생피처 경유만 가능)
- 운영 체인 기본 진입점은 `run_stage1234_chain.sh`이며, Stage5~6은 수동 실행한다.

## L1) 최소 실행 절차

| Stage | 입력 | 출력 | 명령 |
| --- | --- | --- | --- |
| Stage1 | 외부 수집 원천 | `invest/stages/stage1/outputs/{master,raw/signal,raw/qualitative,runtime}` | `python3 invest/stages/stage1/scripts/stage01_daily_update.py` |
| Stage2 | `stage2/inputs/upstream_stage1` | `invest/stages/stage2/outputs/{clean,quarantine,reports,runtime}` | `python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py` + `python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py` |
| Stage3 | `stage3/inputs/{upstream_stage1,upstream_stage2_clean}` | `invest/stages/stage3/outputs/*` | `python3 invest/stages/stage3/scripts/stage03_build_input_jsonl.py` + `python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py --bootstrap-empty-ok` |
| Stage4 | `stage4/inputs/{upstream_stage1_master,upstream_stage2_clean,upstream_stage3_outputs}` | `invest/stages/stage4/outputs/{value,reports}` | `python3 invest/stages/stage4/scripts/calculate_stage4_values.py` |
| Stage5 | `stage5/inputs/{upstream_stage1_master,upstream_stage2_clean,upstream_stage4_value}` | `invest/stages/stage5/outputs/{features,reports}` | `python3 invest/stages/stage5/scripts/stage05_feature_engineer.py` |
| Stage6 | `stage6/inputs/{upstream_stage1,upstream_stage2_clean,upstream_stage4_value,...}` | `invest/stages/stage6/outputs/{results,reports,logs}` | `python3 invest/stages/stage6/scripts/stage06_full_recompute_v4_6_kr.py` |

## L2) 점검 커맨드

```bash
cd "$(git rev-parse --show-toplevel)"

python3 -m py_compile \
  invest/stages/stage1/scripts/stage01_daily_update.py \
  invest/stages/stage2/scripts/stage02_qc_cleaning_full.py \
  invest/stages/stage2/scripts/stage02_onepass_refine_full.py \
  invest/stages/stage3/scripts/stage03_build_input_jsonl.py \
  invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py \
  invest/stages/stage4/scripts/calculate_stage4_values.py \
  invest/stages/stage5/scripts/stage05_feature_engineer.py \
  invest/stages/stage6/scripts/stage06_full_recompute_v4_6_kr.py

bash -n invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh
```

## 수동 실행 순서 (검증용)

```bash
cd "$(git rev-parse --show-toplevel)"

/usr/bin/python3 invest/stages/stage1/scripts/stage01_daily_update.py
/usr/bin/python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py
/usr/bin/python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py
/usr/bin/python3 invest/stages/stage3/scripts/stage03_build_input_jsonl.py
/usr/bin/python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py --bootstrap-empty-ok
/usr/bin/python3 invest/stages/stage4/scripts/calculate_stage4_values.py
/usr/bin/python3 invest/stages/stage5/scripts/stage05_feature_engineer.py
./invest/venv/bin/python invest/stages/stage6/scripts/stage06_full_recompute_v4_6_kr.py
```
