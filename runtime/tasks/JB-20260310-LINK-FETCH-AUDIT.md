# JB-20260310-LINK-FETCH-AUDIT

- reconciled_at: 2026-03-11 15:14:50 KST
- mode: read_only_retained_proof_reconciliation
- status: DONE

## scope
- 텔레그램·블로그 입력의 외부 링크 fetch/link enrichment 경로가 실제로 동작하는지 retained proof만으로 재감사한다.
- live DB writer가 남아 있는 동안 writer/rebuild는 새로 시작하지 않는다.

## retained evidence
1. 초기 live audit (`runtime/tasks/proofs/JB-20260310-LINK-FETCH-AUDIT_live_audit_20260311.json`)
   - `00:14` 시점 authoritative Stage2 output은 과거 `link_enrichment_enabled=false` 산출물로 남아 있었음.
   - 당시 `--force-rebuild` 재시도는 concurrent `stage01_sync_raw_to_db.py` writer 때문에 `sqlite3.OperationalError: database is locked` 로 실패.
2. read-only/lock 보강 proof (`runtime/tasks/proofs/JB-20260310-LINK-FETCH-AUDIT_lock_readonly_fix_20260311.json`)
   - writer lock 하에서도 readonly mirror 접근과 snapshot materialization이 가능함.
   - `raw_db_sync.lock` 직렬화 테스트도 통과.
3. 추가 3회 검증 (`runtime/tasks/proofs/JB-20260310-LINK-FETCH-AUDIT_extra_tests.json`)
   - `blog_html_iana`, `telegram_text_rfc`, `telegram_pdf_dummy` 모두 `ok=true` / `link_enriched=true`.
   - PDF short override 케이스도 기대대로 동작.
4. 후속 야간 observe-only retained proof
   - `runtime/tasks/proofs/JB-20260311-OVERNIGHT-LINK-PDF-CONTROL_20260311_0042.json`: pre-rebuild meta가 `link_enrichment_enabled=false`였고 background forced rebuild가 시작됨.
   - `runtime/tasks/proofs/JB-20260311-OVERNIGHT-LINK-PDF-CONTROL_20260311_0100.json`: authoritative Stage2 processed meta가 `link_enrichment_enabled=true`로 전환됐고, blog clean sample 3건이 모두 `link_enriched=true`.
   - `runtime/tasks/proofs/JB-20260311-OVERNIGHT-LINK-PDF-CONTROL_20260311_0500.json`: telegram `public_fallback` 계열의 `LinkEnriched` 미표시는 short/url-heavy gate를 통과하지 않는 long aggregate 특성 때문이라는 code/path diagnosis가 남아 있음.
   - `runtime/tasks/proofs/JB-20260311-OVERNIGHT-LINK-PDF-CONTROL_20260311_0600.json`: authoritative Stage2 meta `link_enrichment_enabled=true` 유지, raw DB lock holder 없음, observe-only 유지.
   - `runtime/tasks/proofs/JB-20260311-OVERNIGHT-LINK-PDF-CONTROL_20260311_closeout_reconciliation.json`: retained proof 기준 retrospective closeout `DONE` 판정.

## reconciliation
- `00:14`의 BLOCKED 상태는 "기능 미구현" 때문이 아니라, 이미 구현된 link enrichment를 authoritative 산출물에 반영하는 강제 rebuild가 live Stage1 writer lock에 막힌 상황이었다.
- 이후 retained proof는 rebuild 완료 후 authoritative Stage2 meta가 `link_enrichment_enabled=true`로 바뀌었고 blog 경로가 실제 clean output에 반영됐음을 보여준다.
- telegram 경로는 초기엔 sample clean output에 `LinkEnriched` 섹션이 보이지 않아 gap처럼 보였지만, 후속 read-only code/path diagnosis에서 이것이 threshold/format behavior(긴 public_fallback aggregate는 enrichment marker를 새로 붙이지 않는 경로)임이 설명됐다.
- 추가 3회 테스트가 모두 `ok=true`로 남아 있어, 블로그/일반 텍스트 텔레그램/PDF short override까지 링크 fetch 경로 자체는 보강 후 정상으로 판단 가능하다.

## 미확인
- retained proof만으로는 `06:00` 이후 `07:00` 직접 checkpoint snapshot이 보존돼 있지 않다.
- 그러나 이는 본 티켓의 링크 fetch 구현/반영 여부를 다시 BLOCKED로 둘 정도의 live blocker는 아니다.

## verdict
- DONE supportable.
- blocker였던 DB lock은 closeout 시점의 기능 미구현 증거가 아니라, 이미 해결된 authoritative rebuild 타이밍 문제로 정리한다.
- proof set만으로 본 티켓은 닫아도 된다.

## proof
- runtime/tasks/JB-20260310-LINK-FETCH-AUDIT.md
- runtime/tasks/proofs/JB-20260310-LINK-FETCH-AUDIT_live_audit_20260311.json
- runtime/tasks/proofs/JB-20260310-LINK-FETCH-AUDIT_lock_readonly_fix_20260311.json
- runtime/tasks/proofs/JB-20260310-LINK-FETCH-AUDIT_extra_tests.json
- runtime/tasks/proofs/JB-20260311-OVERNIGHT-LINK-PDF-CONTROL_20260311_0100.json
- runtime/tasks/proofs/JB-20260311-OVERNIGHT-LINK-PDF-CONTROL_20260311_0500.json
- runtime/tasks/proofs/JB-20260311-OVERNIGHT-LINK-PDF-CONTROL_20260311_0600.json
- runtime/tasks/proofs/JB-20260311-OVERNIGHT-LINK-PDF-CONTROL_20260311_closeout_reconciliation.json
