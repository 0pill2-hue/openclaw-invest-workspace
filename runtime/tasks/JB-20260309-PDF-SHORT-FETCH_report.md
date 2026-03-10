# JB-20260309-PDF-SHORT-FETCH report

- ticket: JB-20260309-PDF-SHORT-FETCH
- directive: JB-20260309-PDF-SHORT-FETCH
- scope: Stage2 refine/link enrichment에서 PDF direct fetch 및 short-text 허용
- result: PASS

## 변경 사항
1. `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
   - URL link enrichment fetch가 `application/pdf`를 직접 받아 PDF 본문을 추출하도록 추가
   - PDF URL은 본문 길이가 짧아도 `fetched_text_too_short`로 버리지 않도록 예외 처리
   - 짧은 PDF segment도 영문/한글 문자가 있으면 enrichment block에 유지하도록 조정
   - telegram PDF attachment가 promote된 경우 short-text 이유만으로 quarantine하지 않도록 override 추가
   - link enrichment로 들어온 PDF도 short-text만 문제라면 clean 승격되도록 override 추가

## 검증
- `python3 -m py_compile invest/stages/stage2/scripts/stage02_onepass_refine_full.py`

## proof
- invest/stages/stage2/scripts/stage02_onepass_refine_full.py
- runtime/tasks/JB-20260309-PDF-SHORT-FETCH_report.md
