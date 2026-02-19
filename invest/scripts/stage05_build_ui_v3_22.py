#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
W_CSV = BASE / "invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_weights_v3_22_kr.csv"
T_CSV = BASE / "invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_timeline_v3_22_kr.csv"
OUT = BASE / "invest/reports/stage_updates/stage05/v3_22/ui/index.html"


def main():
    wdf = pd.read_csv(W_CSV)
    tdf = pd.read_csv(T_CSV)

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
            }
        )

    dates = sorted(by_date.keys())
    latest = dates[-1] if dates else ""

    payload = {
        "dates": dates,
        "latest": latest,
        "weightsByDate": by_date,
        "timeline": timeline,
        "hhiSeries": hhi_series,
        "top1Series": top1_series,
    }

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
  <div style='margin-top:10px;'>
    기준일: <select id='dateSel'></select>
  </div>
  <div class='row' style='margin-top:10px;'>
    <div class='card kpi'><div class='muted'>보유 종목수</div><div id='kHold'></div></div>
    <div class='card kpi'><div class='muted'>Top1 비중</div><div id='kTop1'></div></div>
    <div class='card kpi'><div class='muted'>HHI</div><div id='kHhi'></div></div>
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
    <table id='tl'><thead><tr><th>일자</th><th>편입</th><th>편출</th><th>근거</th></tr></thead><tbody></tbody></table>
  </div>

<script>
const DATA = {json.dumps(payload, ensure_ascii=False)};
const sel = document.getElementById('dateSel');
DATA.dates.forEach(d => {{ const o=document.createElement('option'); o.value=d; o.textContent=d; sel.appendChild(o); }});
sel.value = DATA.latest;

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
    tr.innerHTML = `<td>${{t.date}}</td><td>${{t.added}}</td><td>${{t.removed}}</td><td>${{t.reason}}</td>`;
    tlb.appendChild(tr);
  }});
}}
sel.addEventListener('change', render);
render();
</script>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(OUT.relative_to(BASE))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
