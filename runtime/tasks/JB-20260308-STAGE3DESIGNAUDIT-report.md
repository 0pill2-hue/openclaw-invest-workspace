# JB-20260308-STAGE3DESIGNAUDIT 보고서

- verdict: REWORK

## key findings
- 현재 Stage3 코드/정본 문서/최신 manifest는 `Stage2 clean + Stage3 reference` 계약을 따르며, Telegram PDF inline 본문과 `selected_articles`도 포함한다.
- 다만 저장소 내 최근 manifest 하나가 여전히 `upstream_stage1` 경로를 기록하고 있어, repo 레벨에서는 "Stage3가 Stage1을 직접 참조하지 않는다"는 계약이 일관되게 정리되지 않았다.
- Stage2→Stage3 계약에 `__NOSYMBOL__` sentinel이 기본 포함되고, Stage3 loader는 `__MACRO__`만 제외하므로 pseudo-symbol이 종목 축으로 전파될 설계 문제가 있다.

## evidence
- Stage2 clean only 계약 / Stage1 직접 입력 금지: `docs/invest/stage3/README.md:6-17`, `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md:9-20`, `docs/invest/stage3/STAGE3_DESIGN.md:11-28`
- 현재 빌더가 참조하는 입력 루트는 Stage2 clean + reference: `invest/stages/stage3/scripts/stage03_build_input_jsonl.py:34-39`, `invest/stages/stage3/scripts/stage03_build_input_jsonl.py:74-82`
- 최신 manifest는 Stage2 clean 경로 사용: `invest/stages/stage3/outputs/manifest_stage3_input_build_20260309_000642.json:15-46`
- 그러나 최근 manifest 하나는 여전히 Stage1 경로 기록: `invest/stages/stage3/outputs/manifest_stage3_input_build_20260308_235946.json:17-29`
- Telegram PDF inline 본문 반영 확인: `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md:13-16`, `invest/stages/stage3/inputs/upstream_stage2_clean/production/qualitative/text/telegram/김찰저의_관심과_생각_저장소_kimcharger_full.md:742-746`, `invest/stages/stage3/inputs/stage2_text_meta_records.jsonl:3266`
- `selected_articles` 포함 확인: `invest/stages/stage3/scripts/stage03_build_input_jsonl.py:82`, `invest/stages/stage3/scripts/stage03_build_input_jsonl.py:758-820`, `invest/stages/stage3/outputs/STAGE3_INPUT_BUILD_latest.json:11`, `invest/stages/stage3/outputs/STAGE3_INPUT_BUILD_latest.json:50-56`
- `__NOSYMBOL__` 기본 주입: `invest/stages/stage3/scripts/stage03_build_input_jsonl.py:586-592`, `invest/stages/stage3/scripts/stage03_build_input_jsonl.py:657-663`, `invest/stages/stage3/scripts/stage03_build_input_jsonl.py:730-738`
- Loader는 `__MACRO__`만 제외하고 나머지 symbol은 그대로 적재: `invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py:424-431`, `invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py:450-477`

## required next action
- 최근 Stage1 경로가 남아 있는 Stage3 manifest를 정리/폐기하거나 legacy로 명시해 계약을 단일화한다.
- `__NOSYMBOL__`는 Stage3 종목 축 집계에서 제외하거나 별도 버킷으로 분리한다.
