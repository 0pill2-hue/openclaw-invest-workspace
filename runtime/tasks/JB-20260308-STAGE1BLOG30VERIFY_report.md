# JB-20260308-STAGE1BLOG30VERIFY report

## 결론
- close_status: DONE
- summary: unresolved 30개 중 29개는 `no-data/terminal`, 1개는 `삭제/404`로 재분류 가능
- rationale: calibration 샘플에서 실제 활성 블로그는 frame `PostView/logNo` 링크와 RSS item이 양수였고, 이번 30개는 그 신호가 전부 0이었다. long_sight는 direct 404로 삭제 근거가 명확하다.

## Calibration (기준점)
| id | direct_status | frame_postview_link_count | frame_logno_query_count | rss_item_count | 해석 |
| --- | ---: | ---: | ---: | ---: | --- |
| danechoi93 | 200 | 0 | 0 | 0 | empty/terminal 패턴 |
| assistant-m | 200 | 0 | 0 | 0 | empty/terminal 패턴 |
| luckyguydb | 200 | 0 | 0 | 0 | empty/terminal 패턴 |
| gaunyu | 200 | 54 | 54 | 50 | 활성/수집 가능 |
| foreconomy | 200 | 12 | 21 | 50 | 활성/수집 가능 |
| investing1004 | 200 | 3 | 6 | 50 | 활성/수집 가능 |

## Probe results
| id | 분류 | direct | frame links | frame logNo | rss items | 근거 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| ssupershy | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| long_sight | 삭제/404 | 404 | None | None | 0 | direct 404 + RSS 0 |
| dragonsoaring | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| gkfn-whddlf | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| balance1987 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| universal_man | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| isimas1004 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| dosangi | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| hjahn07 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| puipuia1 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| bhplayer | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| ksh4243 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| i_mhappy | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| yukkkiii- | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| kmnpsh_ | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| bananakoala | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| ogok2010 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| yjnam7 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| freestyle-good | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| rocky1979 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| kangeungu7 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| akrckd0305 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| snowball1008 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| jakieint | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| hch0714 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| mgheroes | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| rolleiholic | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| tks6028 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| jyt4159 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |
| sjs0330 | no-data/terminal | 200 | 0 | 0 | 0 | direct 200 shell + frame PostView 0 + frame logNo 0 + RSS 0 |

## Count
- no-data/terminal: 29
- 삭제/404: 1

## Proof paths
- runtime/tasks/JB-20260308-STAGE1BLOG30VERIFY_probe.json
- runtime/tasks/JB-20260308-STAGE1BLOG30VERIFY_calibration.json
