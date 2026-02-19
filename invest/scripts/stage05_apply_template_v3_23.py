#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
TEMPLATE = BASE / 'invest/reports/stage_updates/stage05/template'
V23 = BASE / 'invest/reports/stage_updates/stage05/v3_23'


def ensure_dirs():
    (V23 / 'charts').mkdir(parents=True, exist_ok=True)
    (V23 / 'ui').mkdir(parents=True, exist_ok=True)


def load_summary():
    p = V23 / 'summary.json'
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return {}


def write_readable(summary: dict):
    winner = summary.get('winner', '-')
    track = summary.get('winner_track', '-')
    tr = summary.get('winner_return', 0)
    cagr = summary.get('winner_cagr', 0)
    mdd = summary.get('winner_mdd_2021_plus', 0)
    gates = summary.get('gates', {})
    lines = [
        '# stage05_result_v3_23_kr_readable',
        '',
        '## 실행 요약',
        f"- 1위 모델: **{winner}** ({track})",
        f"- 수익률: **{tr*100:.2f}%**",
        f"- CAGR: **{cagr*100:.2f}%**",
        '',
        '## 게이트 요약',
    ]
    for k, v in gates.items():
        lines.append(f"- {k}: {v}")
    lines += [
        '',
        '## 정책 스냅샷',
        '- numeric 최종승자 금지: 적용',
        '- replacement_edge: +15% 기준',
        '',
        '## 성과 요약',
        f"- total_return: {tr*100:.2f}%",
        f"- cagr: {cagr*100:.2f}%",
        '',
        '## MDD 구간 분리',
        f"- mdd_2021_plus: {mdd*100:.2f}%",
        '',
        '## 산출물 경로',
        '- result_md: `invest/reports/stage_updates/stage05/v3_23/stage05_result_v3_23_kr.md`',
        '- readable_md: `invest/reports/stage_updates/stage05/v3_23/stage05_result_v3_23_kr_readable.md`',
        '- charts: `invest/reports/stage_updates/stage05/v3_23/charts/*`',
        '- ui: `invest/reports/stage_updates/stage05/v3_23/ui/index.html`',
        '',
        '## 최종 판정',
        f"- final_decision: {summary.get('final_decision','HOLD_V323_REVIEW_REQUIRED')}",
        f"- stop_reason: {summary.get('stop_reason','REVIEW_REQUIRED')}",
    ]
    (V23 / 'stage05_result_v3_23_kr_readable.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write_patch_diff():
    p = V23 / 'stage05_patch_diff_v3_23_kr.md'
    if p.exists():
        return
    p.write_text(
        '# stage05_patch_diff_v3_23_kr\n\n'
        '- v3_22 템플릿 구조를 기준으로 v3_23 산출물 경로를 정규화함.\n'
        '- 파일명/폴더 구조를 v3_22와 동일 패턴으로 맞춤.\n'
        '- 세부 트레이드 이벤트/타임라인은 v3_23 엔진 확장 시 실데이터로 대체 필요.\n',
        encoding='utf-8'
    )


def write_placeholders():
    trade = V23 / 'stage05_trade_events_v3_23_kr.csv'
    if not trade.exists():
        trade.write_text('buy_date,sell_date,stock_code,stock_name,buy_price,sell_price,pnl,reason\n', encoding='utf-8')

    timeline = V23 / 'stage05_portfolio_timeline_v3_23_kr.csv'
    if not timeline.exists():
        timeline.write_text('rebalance_date,added_codes,removed_codes,kept_codes,replacement_basis,weights_snapshot\n', encoding='utf-8')

    weights = V23 / 'stage05_portfolio_weights_v3_23_kr.csv'
    if not weights.exists():
        weights.write_text('date,stock_code,stock_name,weight_pct,holding_days\n', encoding='utf-8')

    ws = V23 / 'stage05_portfolio_weights_summary_v3_23_kr.json'
    if not ws.exists():
        ws.write_text(json.dumps({'status': 'DRAFT_TEMPLATE_ONLY', 'note': 'v3_23 engine extension required for weight snapshots'}, ensure_ascii=False, indent=2), encoding='utf-8')


def copy_charts_and_ui():
    cont = V23 / 'charts/stage05_v3_23_yearly_continuous_2021plus.png'
    reset = V23 / 'charts/stage05_v3_23_yearly_reset_2021plus.png'
    if cont.exists():
        (V23 / 'charts/stage05_v3_23_cum_2021plus.png').write_bytes(cont.read_bytes())
        (V23 / 'charts/stage05_eval_yearly_continuous_2021plus.png').write_bytes(cont.read_bytes())
    else:
        tp = TEMPLATE / 'charts/stage05_eval_yearly_continuous_2021plus.png'
        if tp.exists():
            (V23 / 'charts/stage05_eval_yearly_continuous_2021plus.png').write_bytes(tp.read_bytes())
    if reset.exists():
        (V23 / 'charts/stage05_eval_yearly_reset_2021plus.png').write_bytes(reset.read_bytes())
    else:
        tp = TEMPLATE / 'charts/stage05_eval_yearly_reset_2021plus.png'
        if tp.exists():
            (V23 / 'charts/stage05_eval_yearly_reset_2021plus.png').write_bytes(tp.read_bytes())

    dash = V23 / 'ui/dashboard.html'
    idx = V23 / 'ui/index.html'
    if dash.exists():
        idx.write_text(dash.read_text(encoding='utf-8'), encoding='utf-8')
    else:
        tp = TEMPLATE / 'ui/index.html'
        if tp.exists():
            idx.write_text(tp.read_text(encoding='utf-8'), encoding='utf-8')


def main():
    ensure_dirs()
    summary = load_summary()
    write_readable(summary)
    write_patch_diff()
    write_placeholders()
    copy_charts_and_ui()
    print(json.dumps({'status': 'ok', 'v3_23': str(V23.relative_to(BASE))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
