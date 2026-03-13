# web-review templates

역할: **web-review 질문/응답 템플릿 문서**.

상위 문서: `docs/operations/skills/web-review.md`

## 1. 기본 질문 템플릿
```txt
Use ONLY this baseline:
- repo: <repo_name>
- repo_url: <github_repo_url>
- branch: <branch_name>
- commit: <commit_hash>
- commit_url: <github_commit_url_if_available>

Ignore all prior conversation/context/memory.
If the commit alone is not enough, return NEED_MORE_CONTEXT instead of guessing.

Goal:
<1-3 short lines>

Scope:
- area: <folder / subsystem / docset>
- read: <read all relevant docs/code under this scope>
- focus: <must-fix issues / contradictions / best improvements>

Optional minimal context (only if needed):
- anchor files: <a few representative paths>
- tiny diff/snippet: <minimum only>

Return ONLY one JSON code block.
No prose.
```

## 2. 고정 응답 포맷
### preferred JSON
```json
{"decision":"APPLY|REJECT|NEED_MORE_CONTEXT","must_fix":["..."],"improvements":["..."],"risks":["..."],"token_cost":"LOW|MEDIUM|HIGH","questions":["..."]}
```

### ultra-short fallback
```txt
APPLY|REJECT|NEED_MORE_CONTEXT
- must_fix: <none or short item>
- improvement: <short item>
- token_cost: LOW|MEDIUM|HIGH - <short reason>
```

## 3. prompt 작성 메모
- baseline은 branch + commit_hash 중심으로 고정
- 이전 컨텍스트 무시를 반드시 명시
- long prose 금지
- private repo라 commit만으로 부족하면 최소 diff/snippet만 추가
- area는 file-level보다 folder/subsystem 단위가 기본

## 4. direct attachment 메모
- 실제 파일 자체를 첨부한다.
- 첨부칩/리스트가 composer에 보이는지 확인한다.
- 첨부 수가 많으면 fresh chat 기준 20파일 이하로 분할한다.
- 전송이 막히면 `Enter -> Meta+Enter` 순으로 시도한다.

## 5. watch 메모
- `APPLY|REJECT|NEED_MORE_CONTEXT` 토큰만 기다리지 않는다.
- JSON 또는 JSON-shaped 답변이면 정상 수집으로 본다.
