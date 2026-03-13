# Stage1 Docs

Stage1 문서는 contract와 operations를 분리해 유지한다.

## 문서 역할
| 파일 | 역할 |
| --- | --- |
| `README.md` | Stage1 진입 인덱스 |
| `STAGE1_RULEBOOK_AND_REPRO.md` | stage contract/repro SSOT |
| `RUNBOOK.md` | operations SSOT (실행/스케줄/장애대응) |
| `stage01_data_collection.md` | collector별 artifact 최소 스키마 appendix |
| `TODO.md` | tracked backlog |

## 충돌 해소 우선순위
1. 실행 절차/명령/환경변수/스케줄 충돌: `RUNBOOK.md`
2. 범위/입출력/게이트/판정 충돌: `STAGE1_RULEBOOK_AND_REPRO.md`
3. artifact 스키마 충돌: `stage01_data_collection.md`

## 바로가기
- [STAGE1_RULEBOOK_AND_REPRO.md](./STAGE1_RULEBOOK_AND_REPRO.md)
- [RUNBOOK.md](./RUNBOOK.md)
- [stage01_data_collection.md](./stage01_data_collection.md)
- [TODO.md](./TODO.md)
