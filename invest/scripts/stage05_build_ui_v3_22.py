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
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def main():
    wdf = pd.read_csv(W_CSV)
    tdf = pd.read_csv(T_CSV)
    _ = pd.read_csv(E_CSV) if E_CSV.exists() else pd.DataFrame()

    if "stock_code" not in wdf.columns:
        wdf["stock_code"] = ""

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

    dates = sorted(by_date.keys())
    latest = dates[-1] if dates else ""

    weight_map = {}
    for d, items in by_date.items():
        wm = {}
        for it in items:
            wm[str(it["stock_name"])] = float(it["weight_pct"])
        weight_map[d] = wm

    timeline = []
    for r in tdf.fillna("-").itertuples():
        d = str(r.rebalance_date)
        prev_dates = [x for x in dates if x < d]
        prev_d = prev_dates[-1] if prev_dates else None
        cur_w = weight_map.get(d, {})
        prev_w = weight_map.get(prev_d, {}) if prev_d else {}

        def _fmt_with_pct(codes_text, wmap):
            if not codes_text or str(codes_text).strip() in {"", "-"}:
                return "-"
            out = []
            for name in [x.strip() for x in str(codes_text).split(",") if x.strip()]:
                pct = wmap.get(name)
                if pct is None:
                    out.append(name)
                else:
                    out.append(f"{name} {pct:.1f}%")
            return ", ".join(out) if out else "-"

        timeline.append(
            {
                "date": d,
                "added": _fmt_with_pct(str(r.added_codes), cur_w),
                "removed": _fmt_with_pct(str(r.removed_codes), prev_w),
                "reason": str(r.replacement_basis),
                "current": str(getattr(r, "weights_snapshot", "-")),
            }
        )

    payload = {
        "dates": dates,
        "latest": latest,
        "weightsByDate": by_date,
        "timeline": timeline,
        "hhiSeries": hhi_series,
        "top1Series": top1_series,
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
    th,td {{ border-bottom:1px solid #2b3240; padding:8px; font-size:13px; text-align:left; vertical-align:top; }}
    .muted {{ color:#9aa4b2; font-size:12px; }}
    select {{ background:#171a21; color:#e8ecf1; border:1px solid #2b3240; padding:6px; border-radius:8px; }}
    .btn {{ background:#202634; color:#dbe7ff; border:1px solid #32435e; border-radius:8px; padding:2px 8px; cursor:pointer; font-size:12px; }}
    .modal {{ position:fixed; inset:0; background:rgba(0,0,0,.6); display:none; align-items:center; justify-content:center; z-index:999; }}
    .panel {{ width:min(900px,95vw); max-height:90vh; overflow:auto; background:#171a21; border:1px solid #2b3240; border-radius:10px; padding:12px; }}
    .legend-item {{ font-size:12px; margin:2px 0; }}
  </style>
</head>
<body>
  <h2>Stage05 v3_22 포트폴리오 비중 UI</h2>
  <div class='muted'>리밸런싱 변화 + 포트 비중 원형그래프</div>

  <div class='row' style='margin-top:10px;'>
    <div class='card kpi'><div class='muted'>보유 종목수</div><div id='kHold'></div></div>
    <div class='card kpi'><div class='muted'>Top1 비중</div><div id='kTop1'></div></div>
    <div class='card kpi'><div class='muted'>HHI</div><div id='kHhi'></div></div>
  </div>

  <div class='card' style='margin-top:12px;'>
    <h3>평가 차트 (고정)</h3>
    <div style='margin-top:10px;'>
      <div><b>누적 평가용</b></div>
      <img src='{chart_cont_src}' style='width:100%;max-width:1200px;border:1px solid #2b3240;border-radius:8px;margin-top:6px;' />
    </div>
    <div style='margin-top:14px;'>
      <div><b>연도별 리셋 평가용</b></div>
      <img src='{chart_reset_src}' style='width:100%;max-width:1200px;border:1px solid #2b3240;border-radius:8px;margin-top:6px;' />
    </div>
    <div style='margin-top:12px;'>기준일: <select id='dateSel'></select></div>
  </div>

  <div class='card' style='margin-top:12px;'>
    <h3>리밸런싱 변화표</h3>
    <table id='tl'><thead><tr><th>일자</th><th>편입</th><th>편출</th><th>근거</th><th>현재 포트폴리오(비중)</th><th>상세</th></tr></thead><tbody></tbody></table>
    <div style='display:flex;justify-content:center;gap:8px;align-items:center;margin-top:10px;'>
      <button id='prevPage' class='btn'>◀ 이전</button>
      <span id='pageInfo' class='muted'>1 / 1</span>
      <button id='nextPage' class='btn'>다음 ▶</button>
    </div>
  </div>

  <div id='pieModal' class='modal'>
    <div class='panel'>
      <div style='display:flex;justify-content:space-between;align-items:center;'>
        <h3 id='pieTitle'>포트폴리오 원형그래프</h3>
        <button id='closeModal' class='btn'>닫기</button>
      </div>
      <canvas id='pieCanvas' width='520' height='520' style='max-width:100%;background:#0f1115;border-radius:8px;'></canvas>
      <div id='pieLegend' style='margin-top:10px;'></div>
    </div>
  </div>

<script>
const DATA = {json.dumps(payload, ensure_ascii=False)};
const sel = document.getElementById('dateSel');
const PAGE_SIZE = 20;
let timelinePage = 1;
DATA.dates.forEach(d => {{ const o=document.createElement('option'); o.value=d; o.textContent=d; sel.appendChild(o); }});
sel.value = DATA.latest;

function parseCurrentPortfolio(text) {{
  if (!text || text === '-') return [];
  return String(text).split(';').map(x=>x.trim()).filter(Boolean).map(row => {{
    const m = row.match(/^(.*)\s([0-9.]+)%/);
    if (!m) return null;
    return {{ name: m[1].trim(), w: parseFloat(m[2]) }};
  }}).filter(Boolean);
}}

function drawPie(items, title) {{
  const modal = document.getElementById('pieModal');
  const c = document.getElementById('pieCanvas');
  const ctx = c.getContext('2d');
  const legend = document.getElementById('pieLegend');
  document.getElementById('pieTitle').textContent = title;
  ctx.clearRect(0,0,c.width,c.height);
  legend.innerHTML = '';

  if (!items.length) {{
    ctx.fillStyle='#9aa4b2';
    ctx.font='16px sans-serif';
    ctx.fillText('데이터 없음', 210, 260);
    modal.style.display='flex';
    return;
  }}

  const colors = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf'];
  let total = items.reduce((a,b)=>a+b.w,0);
  let start = -Math.PI/2;
  const cx=260, cy=260, r=190;

  items.forEach((it, idx) => {{
    const frac = it.w / total;
    const end = start + frac * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx,cy);
    ctx.arc(cx,cy,r,start,end);
    ctx.closePath();
    ctx.fillStyle = colors[idx % colors.length];
    ctx.fill();
    start = end;

    const div = document.createElement('div');
    div.className='legend-item';
    div.innerHTML = `<span style="display:inline-block;width:10px;height:10px;background:${{colors[idx % colors.length]}};margin-right:6px;"></span>${{it.name}} - ${{it.w.toFixed(1)}}%`;
    legend.appendChild(div);
  }});

  modal.style.display='flex';
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

  const tlb = document.querySelector('#tl tbody'); tlb.innerHTML='';
  const ordered = [...(DATA.timeline || [])].reverse();
  const totalPages = Math.max(1, Math.ceil(ordered.length / PAGE_SIZE));
  if (timelinePage > totalPages) timelinePage = totalPages;
  const start = (timelinePage - 1) * PAGE_SIZE;
  const pageRows = ordered.slice(start, start + PAGE_SIZE);
  pageRows.forEach(t => {{
    const tr=document.createElement('tr');
    tr.innerHTML = '<td>' + t.date + '</td>'
      + '<td>' + (t.added || '-') + '</td>'
      + '<td>' + (t.removed || '-') + '</td>'
      + '<td>' + (t.reason || '-') + '</td>'
      + '<td>' + (t.current || '-') + '</td>'
      + '<td><button class="btn">더보기</button></td>';
    tr.querySelector('button').addEventListener('click', () => {{
      const items = parseCurrentPortfolio(t.current || '-');
      drawPie(items, `포트폴리오 비중 - ${{t.date}}`);
    }});
    tlb.appendChild(tr);
  }});

  document.getElementById('pageInfo').textContent = timelinePage + ' / ' + totalPages;
  document.getElementById('prevPage').disabled = timelinePage <= 1;
  document.getElementById('nextPage').disabled = timelinePage >= totalPages;
}}

sel.addEventListener('change', render);
document.getElementById('prevPage').addEventListener('click', () => {{ if (timelinePage > 1) {{ timelinePage -= 1; render(); }} }});
document.getElementById('nextPage').addEventListener('click', () => {{ const totalPages = Math.max(1, Math.ceil((DATA.timeline || []).length / PAGE_SIZE)); if (timelinePage < totalPages) {{ timelinePage += 1; render(); }} }});
document.getElementById('closeModal').addEventListener('click', () => {{ document.getElementById('pieModal').style.display='none'; }});
document.getElementById('pieModal').addEventListener('click', (e) => {{ if (e.target.id === 'pieModal') document.getElementById('pieModal').style.display='none'; }});
render();
</script>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(OUT.relative_to(BASE))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
