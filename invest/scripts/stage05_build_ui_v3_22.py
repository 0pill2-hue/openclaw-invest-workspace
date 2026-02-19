#!/usr/bin/env python3
from __future__ import annotations
import base64
import json
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
W_CSV = BASE / "invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_weights_v3_22_kr.csv"
T_CSV = BASE / "invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_timeline_v3_22_kr.csv"
E_CSV = BASE / "invest/reports/stage_updates/stage05/v3_22/stage05_trade_events_v3_22_kr.csv"
OUT = BASE / "invest/reports/stage_updates/stage05/v3_22/ui/index.html"
CHART_CONT = BASE / "invest/reports/stage_updates/stage05/v3_22/charts/stage05_v3_22_yearly_continuous_2021plus.png"
CHART_RESET = BASE / "invest/reports/stage_updates/stage05/v3_22/charts/stage05_v3_22_yearly_reset_2021plus.png"


def _img_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode('ascii')
    return f"data:image/png;base64,{b64}"


def main():
    wdf = pd.read_csv(W_CSV)
    tdf = pd.read_csv(T_CSV)
    edf = pd.read_csv(E_CSV) if E_CSV.exists() else pd.DataFrame()

    if "stock_code" not in wdf.columns:
        wdf["stock_code"] = ""

    # normalize
    wdf["date"] = wdf["date"].astype(str)
    wdf["weight_pct"] = pd.to_numeric(wdf["weight_pct"], errors="coerce").fillna(0.0)
    wdf["holding_days"] = pd.to_numeric(wdf["holding_days"], errors="coerce").fillna(0).astype(int)

    by_date = {}
    hhi_series = []
    top1_series = []
    for d, g in wdf.groupby("date"):
        g = g.sort_values("weight_pct", ascending=False)
        items = [
            {
                "stock_name": str(r.stock_name),
                "stock_code": str(r.stock_code),
                "weight_pct": round(float(r.weight_pct), 2),
                "holding_days": int(r.holding_days),
            }
            for r in g.itertuples()
        ]
        by_date[d] = items
        ws = [x["weight_pct"] / 100.0 for x in items]
        hhi = float(sum(v * v for v in ws)) if ws else 0.0
        top1 = float(items[0]["weight_pct"]) if items else 0.0
        hhi_series.append({"date": d, "hhi": round(hhi, 4)})
        top1_series.append({"date": d, "top1": round(top1, 2)})

    # timeline changes
    timeline = []
    for r in tdf.fillna("-").itertuples():
        timeline.append(
            {
                "date": str(r.rebalance_date),
                "added": str(r.added_codes),
                "removed": str(r.removed_codes),
                "kept": str(r.kept_codes),
                "reason": str(r.replacement_basis),
                "current": str(getattr(r, 'weights_snapshot', '-')),
            }
        )

    dates = sorted(by_date.keys())
    latest = dates[-1] if dates else ""

    events = []
    if not edf.empty:
        for _, r in edf.fillna('').iterrows():
            bd = str(r.get('buy_date', '')).strip()
            sd = str(r.get('sell_date', '')).strip()
            nm = str(r.get('stock_name', '')).strip() or str(r.get('stock_code', '')).strip()
            if bd:
                events.append({'date': bd, 'type': 'BUY', 'name': nm})
            if sd:
                events.append({'date': sd, 'type': 'SELL', 'name': nm})
    events = sorted(events, key=lambda x: x['date'], reverse=True)[:80]

    payload = {
        "dates": dates,
        "latest": latest,
        "weightsByDate": by_date,
        "timeline": timeline,
        "hhiSeries": hhi_series,
        "top1Series": top1_series,
        "events": events,
    }

    chart_cont_src = _img_data_uri(CHART_CONT)
    chart_reset_src = _img_data_uri(CHART_RESET)

    html = f"""<!doctype html>
<html lang='ko'>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>Stage05 v3_22 Portfolio UI</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; margin: 20px; background:#0f1115; color:#e8ecf1; }}
    .row {{ display:flex; gap:12px; flex-wrap:wrap; }}
    .card {{ background:#171a21; border:1px solid #2b3240; border-radius:10px; padding:12px; }}
    .kpi {{ min-width:180px; }}
    table {{ border-collapse: collapse; width:100%; margin-top:10px; }}
    th,td {{ border-bottom:1px solid #2b3240; padding:8px; font-size:13px; text-align:left; }}
    .bar {{ background:#2b3240; border-radius:6px; height:16px; position:relative; overflow:hidden; }}
    .fill {{ background:#4c8bf5; height:100%; }}
    .muted {{ color:#9aa4b2; font-size:12px; }}
    select {{ background:#171a21; color:#e8ecf1; border:1px solid #2b3240; padding:6px; border-radius:8px; }}
  </style>
</head>
<body>
  <h2>Stage05 v3_22 포트폴리오 비중 UI</h2>
  <div class='muted'>읽기용 카드 + 변화표 + 집중도 지표</div>
  <div class='row' style='margin-top:10px;'>
    <div class='card kpi'><div class='muted'>보유 종목수</div><div id='kHold'></div></div>
    <div class='card kpi'><div class='muted'>Top1 비중</div><div id='kTop1'></div></div>
    <div class='card kpi'><div class='muted'>HHI</div><div id='kHhi'></div></div>
  </div>

  <div class='card' style='margin-top:12px;'>
    <h3>평가 차트 (고정)</h3>
    <div class='muted'>기존 생성 차트를 이 페이지에서 바로 확인합니다.</div>
    <div style='margin-top:10px;'>
      <div><b>누적 평가용 (yearly_continuous, 이벤트 포함)</b></div>
      <img src='{chart_cont_src}' style='width:100%;max-width:1200px;border:1px solid #2b3240;border-radius:8px;margin-top:6px;' />
    </div>
    <div style='margin-top:14px;'>
      <div><b>연도별 리셋 평가용 (yearly_reset, 이벤트 포함)</b></div>
      <img src='{chart_reset_src}' style='width:100%;max-width:1200px;border:1px solid #2b3240;border-radius:8px;margin-top:6px;' />
    </div>
    <div style='margin-top:12px;'>
      기준일: <select id='dateSel'></select>
    </div>
    <div style='margin-top:10px;'>
      <div class='muted'>이벤트 클릭 시 기준일 자동 선택</div>
      <div id='eventChips' style='display:flex;flex-wrap:wrap;gap:6px;max-height:120px;overflow:auto;'></div>
    </div>
    <div class='muted' style='margin-top:8px;'>원본: {CHART_CONT}, {CHART_RESET}</div>
  </div>

  <div class='card' style='margin-top:12px;'>
    <h3>종목 비중 Top5</h3>
    <div id='top5'></div>
  </div>

  <div class='card' style='margin-top:12px;'>
    <h3>전 종목 비중표</h3>
    <table id='tbl'><thead><tr><th>종목</th><th>비중</th><th>보유일수</th></tr></thead><tbody></tbody></table>
  </div>

  <div class='card' style='margin-top:12px;'>
    <h3>리밸런싱 변화표</h3>
    <table id='tl'><thead><tr><th>일자</th><th>편입</th><th>편출</th><th>근거</th><th>현재 포트폴리오(비중)</th></tr></thead><tbody></tbody></table>
  </div>

<script>
const DATA = {json.dumps(payload, ensure_ascii=False)};
const sel = document.getElementById('dateSel');
DATA.dates.forEach(d => {{ const o=document.createElement('option'); o.value=d; o.textContent=d; sel.appendChild(o); }});
sel.value = DATA.latest;

function nearestDate(target) {{
  if (!DATA.dates || DATA.dates.length === 0) return null;
  const t = new Date(target).getTime();
  let best = DATA.dates[0], bestDiff = Math.abs(new Date(DATA.dates[0]).getTime() - t);
  for (const d of DATA.dates) {{
    const diff = Math.abs(new Date(d).getTime() - t);
    if (diff < bestDiff) {{ best = d; bestDiff = diff; }}
  }}
  return best;
}}

function renderEventChips() {{
  const box = document.getElementById('eventChips');
  box.innerHTML = '';
  (DATA.events || []).slice(0, 60).forEach(ev => {{
    const b = document.createElement('button');
    b.textContent = `${{ev.date}} ${{ev.type}} ${{ev.name}}`;
    b.style.cssText = 'background:#202634;color:#dbe7ff;border:1px solid #32435e;border-radius:999px;padding:4px 8px;cursor:pointer;font-size:12px;';
    b.onclick = () => {{
      const nd = nearestDate(ev.date);
      if (nd) {{ sel.value = nd; render(); }}
    }};
    box.appendChild(b);
  }});
}}

function render() {{
  const d = sel.value;
  const rows = (DATA.weightsByDate[d] || []);
  const hold = rows.length;
  const top1 = hold? rows[0].weight_pct:0;
  const hhi = rows.reduce((a,r)=>a+Math.pow(r.weight_pct/100,2),0);

  document.getElementById('kHold').textContent = hold + '개';
  document.getElementById('kTop1').textContent = top1.toFixed(2) + '%';
  document.getElementById('kHhi').textContent = hhi.toFixed(4);

  const top5 = rows.slice(0,5).map(r => `
    <div style='margin:8px 0;'>
      <div style='display:flex;justify-content:space-between;'><span>${{r.stock_name}}</span><span>${{r.weight_pct.toFixed(2)}}%</span></div>
      <div class='bar'><div class='fill' style='width:${{Math.max(0,Math.min(100,r.weight_pct))}}%'></div></div>
      <div class='muted'>보유일수 ${{r.holding_days}}d</div>
    </div>`).join('');
  document.getElementById('top5').innerHTML = top5 || '<div class="muted">데이터 없음</div>';

  const tb = document.querySelector('#tbl tbody'); tb.innerHTML='';
  rows.forEach(r => {{
    const tr=document.createElement('tr');
    tr.innerHTML = `<td>${{r.stock_name}}</td><td>${{r.weight_pct.toFixed(2)}}%</td><td>${{r.holding_days}}d</td>`;
    tb.appendChild(tr);
  }});

  const tlb = document.querySelector('#tl tbody'); tlb.innerHTML='';
  DATA.timeline.slice(-20).reverse().forEach(t => {{
    const tr=document.createElement('tr');
    tr.innerHTML = `<td>${{t.date}}</td><td>${{t.added}}</td><td>${{t.removed}}</td><td>${{t.reason}}</td><td>${{t.current}}</td>`;
    tlb.appendChild(tr);
  }});
}}
sel.addEventListener('change', render);
renderEventChips();
render();
</script>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(OUT.relative_to(BASE))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
