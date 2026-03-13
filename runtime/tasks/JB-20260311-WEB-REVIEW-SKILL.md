# JB-20260311-WEB-REVIEW-SKILL

- status: READY_FOR_REVIEW
- started_at: 2026-03-11 17:35 KST
- updated_at: 2026-03-11 17:40 KST
- close_recommendation: DONE

## goal
- 웹페이지의 ChatGPT Pro에게 현재 GitHub 최신 commit hash 기준으로 직접 묻고, 긴 설명 없이 짧은 코드블록 답변만 받아 실제 적용 여부를 판단·적용하는 스킬을 만든다.

## accomplished
1. custom skill `web-review`를 생성했다.
   - path: `/Users/jobiseu/.agents/skills/web-review/SKILL.md`
2. 스킬 규약에 아래 hard rule을 반영했다.
   - 사용 전 반드시 `git commit` + `git push`
   - `branch + commit_hash`를 기준 baseline으로 고정
   - 기존 컨텍스트/이전 대화 무시를 프롬프트에 명시
   - 답변은 짧은 코드블록(JSON 우선)만 허용
   - 웹 답변은 조비스가 검토 후 APPLY/REJECT/NEED_MORE_CONTEXT 판단
3. 수동 웹 단계는 browser automation 없이도 쓸 수 있게 설계했다.
4. 오늘 20:00 KST 리마인더(cron)를 이미 연결해 두었다.

## exact proof paths
- skill: `/Users/jobiseu/.agents/skills/web-review/SKILL.md`
- task report: `runtime/tasks/JB-20260311-WEB-REVIEW-SKILL.md`
- reminder job id: `b81750e1-1d68-4ffc-b864-260a4794f1de`

## notes
- 현재 환경에는 브라우저 자동조작 툴이 없으므로 ChatGPT Pro 웹 입력/응답은 주인님 수동 단계가 필요하다.
- commit hash만으로 부족한 private context가 있으면 최소한의 파일경로/짧은 diff만 추가하는 방식으로 설계했다.
- 스킬 생성 자체는 완료로 볼 수 있고, 오늘 20:00 KST에는 실제 사용 준비 확인만 하면 된다.
