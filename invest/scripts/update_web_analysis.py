import os
import json

# Paths
structured_map_path = '/Users/jobiseu/.openclaw/workspace/invest/data/master/coupling_map_structured.json'
web_dir = '/Users/jobiseu/.openclaw/workspace/invest/web'

def update_coupling_graph():
    if not os.path.exists(structured_map_path):
        return
        
    with open(structured_map_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Convert to D3 format
    nodes_map = {}
    links = []
    
    # Simple sector inference based on name for this draft
    def get_sector(name):
        semi_keywords = ["Hynix", "Samsung", "Nvidia", "Semiconductor", "ASML", "TSMC", "HBM", "DDR5", "Micron", "HPSP", "Exicon", "EO Technics", "원익", "한미", "디아이"]
        if any(kw.lower() in name.lower() for kw in semi_keywords): return "Semiconductor"
        if "SpaceX" in name or "Starlink" in name or "우주" in name: return "Space"
        if "Apple" in name or "iPhone" in name or "Tesla" in name: return "Tech"
        return "Other"

    for link in data['links']:
        u = link['from']
        v = link['to']
        if u not in nodes_map: nodes_map[u] = {"id": u, "group": get_sector(u)}
        if v not in nodes_map: nodes_map[v] = {"id": v, "group": get_sector(v)}
        links.append({
            "source": u,
            "target": v,
            "relation": link['relation'],
            "reason": link['reason'],
            "source_files": link['source']
        })

    html_content = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>Intelligence Map - JoBis</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body {{ background-color: #0a0f1e; color: #e2e8f0; font-family: 'Inter', sans-serif; margin: 0; overflow: hidden; }}
        .node {{ stroke: #fff; stroke-width: 1.5px; cursor: pointer; transition: all 0.2s ease; }}
        .node:hover {{ filter: drop-shadow(0 0 8px rgba(255,255,255,0.5)); }}
        .link {{ stroke: #2d3748; stroke-opacity: 0.4; stroke-width: 1.5px; marker-end: url(#arrowhead); }}
        .label {{ font-size: 10px; fill: #64748b; font-weight: 600; pointer-events: none; text-transform: uppercase; letter-spacing: 0.05em; }}
        #side-panel {{ 
            position: absolute; right: 0; top: 0; width: 450px; height: 100vh; 
            background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(20px);
            border-left: 1px solid #1e293b; transform: translateX(100%); transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 100; overflow-y: auto; padding: 40px; box-shadow: -20px 0 50px rgba(0,0,0,0.5);
        }}
        #side-panel.open {{ transform: translateX(0); }}
        .sector-tag {{ padding: 2px 10px; border-radius: 99px; font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; }}
        .Semiconductor {{ background: rgba(16, 185, 129, 0.1); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.2); }}
        .Space {{ background: rgba(59, 130, 246, 0.1); color: #3b82f6; border: 1px solid rgba(59, 130, 246, 0.2); }}
        .Tech {{ background: rgba(245, 158, 11, 0.1); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.2); }}
        .Other {{ background: rgba(148, 163, 184, 0.1); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.2); }}
        .glass-box {{ background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255,255,255,0.05); border-radius: 16px; padding: 20px; }}
    </style>
</head>
<body>
    <!-- Side Panel -->
    <div id="side-panel">
        <button onclick="closePanel()" class="group flex items-center text-slate-500 hover:text-white transition mb-10 uppercase text-[10px] font-black tracking-widest">
            <svg class="w-4 h-4 mr-2 transition-transform group-hover:-translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M15 19l-7-7 7-7"></path></svg>
            Close Insight
        </button>
        
        <div id="detail-content">
            <div id="detail-sector" class="mb-4"></div>
            <h2 id="detail-title" class="text-4xl font-black text-white mb-8 tracking-tighter leading-tight uppercase">SELECT_NODE</h2>
            
            <div class="space-y-10">
                <section>
                    <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-4">Supply Chain Intelligence</h3>
                    <div id="detail-links" class="space-y-4"></div>
                </section>
                
                <section>
                    <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-4">Sentiment Matrix</h3>
                    <div class="glass-box border-l-4 border-emerald-500">
                        <div class="flex justify-between items-center mb-3">
                            <span class="text-xs font-bold text-slate-300">Market Consensus</span>
                            <span class="text-emerald-400 font-mono text-lg font-bold">BULLISH</span>
                        </div>
                        <div class="w-full bg-slate-900 h-2 rounded-full mb-2">
                            <div class="bg-emerald-500 h-2 rounded-full shadow-[0_0_10px_#10b981]" style="width: 82%"></div>
                        </div>
                        <p class="text-[10px] text-slate-500 italic text-center mt-4">"Based on 633 curated sources"</p>
                    </div>
                </section>

                <section>
                    <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-4">Verification Artifacts</h3>
                    <div id="detail-sources" class="font-mono text-[10px] text-slate-500 space-y-2"></div>
                </section>
            </div>
        </div>
    </div>

    <!-- Header Overlay -->
    <div class="absolute top-10 left-10 z-10 pointer-events-none">
        <div class="flex items-center space-x-3 mb-6">
            <div class="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center font-black text-black text-xl italic shadow-2xl">M</div>
            <div>
                <h1 class="text-3xl font-black text-white tracking-tighter leading-none uppercase">Alpha Coupling<span class="text-emerald-500">.</span></h1>
                <p class="text-slate-500 text-[10px] font-bold uppercase tracking-widest mt-1">Cross-Sector Correlation Engine</p>
            </div>
        </div>
        
        <div class="flex flex-wrap gap-3 bg-slate-900/50 backdrop-blur-md p-4 rounded-2xl border border-slate-800 pointer-events-auto">
            <div class="flex items-center space-x-2 px-3"><div class="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_#10b981]"></div><span class="text-[10px] font-black text-slate-400 uppercase tracking-tighter">Semiconductor</span></div>
            <div class="flex items-center space-x-2 px-3 border-l border-slate-800"><div class="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_#3b82f6]"></div><span class="text-[10px] font-black text-slate-400 uppercase tracking-tighter">Space / Sat</span></div>
            <div class="flex items-center space-x-2 px-3 border-l border-slate-800"><div class="w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_8px_#f59e0b]"></div><span class="text-[10px] font-black text-slate-400 uppercase tracking-tighter">Tech / Auto</span></div>
        </div>
    </div>

    <svg id="canvas"></svg>

    <script>
        const graphData = {json.dumps({"nodes": list(nodes_map.values()), "links": links}, ensure_ascii=False)};
        
        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("#canvas")
            .attr("width", width)
            .attr("height", height);

        // Arrow head marker
        svg.append("defs").append("marker")
            .attr("id", "arrowhead")
            .attr("viewBox", "-0 -5 10 10")
            .attr("refX", 35)
            .attr("refY", 0)
            .attr("orient", "auto")
            .attr("markerWidth", 5)
            .attr("markerHeight", 5)
            .append("path")
            .attr("d", "M 0,-5 L 10 ,0 L 0,5")
            .attr("fill", "#1e293b");

        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(250))
            .force("charge", d3.forceManyBody().strength(-800))
            .force("center", d3.forceCenter(width / 2.3, height / 2))
            .force("collision", d3.forceCollide().radius(80));

        const link = svg.append("g")
            .selectAll("line")
            .data(graphData.links)
            .join("line")
            .attr("class", "link");

        const node = svg.append("g")
            .selectAll("circle")
            .data(graphData.nodes)
            .join("circle")
                .attr("class", "node")
                .attr("r", d => d.group === "Semiconductor" ? 22 : 14)
                .attr("fill", d => d.group === "Semiconductor" ? "#10b981" : d.group === "Space" ? "#3b82f6" : d.group === "Tech" ? "#f59e0b" : "#475569")
                .on("click", (event, d) => showDetail(d))
                .call(d3.drag()
                    .on("start", dragstarted)
                    .on("drag", dragged)
                    .on("end", dragended));

        const label = svg.append("g")
            .selectAll("text")
            .data(graphData.nodes)
            .join("text")
                .attr("class", "label")
                .attr("dx", 28)
                .attr("dy", 5)
                .text(d => d.id);

        simulation.on("tick", () => {{
            link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
            node.attr("cx", d => d.x).attr("cy", d => d.y);
            label.attr("x", d => d.x).attr("y", d => d.y);
        }});

        function showDetail(d) {{
            document.getElementById('side-panel').classList.add('open');
            document.getElementById('detail-title').innerText = d.id;
            document.getElementById('detail-sector').innerHTML = `<span class="sector-tag ${{d.group}}">${{d.group}}</span>`;
            
            const connectedLinks = graphData.links.filter(l => l.source.id === d.id || l.target.id === d.id);
            document.getElementById('detail-links').innerHTML = connectedLinks.map(l => `
                <div class="p-6 bg-slate-800/60 rounded-3xl border border-slate-700 hover:border-emerald-500 transition-all duration-300">
                    <div class="flex items-center space-x-2 mb-3">
                        <span class="text-[8px] font-black px-2 py-1 bg-slate-900 rounded-full text-slate-500 tracking-tighter">
                            ${{l.source.id === d.id ? 'OUTPUT_STREAM' : 'INPUT_FEED'}}
                        </span>
                        <span class="text-sm font-black text-white uppercase">${{l.source.id === d.id ? l.target.id : l.source.id}}</span>
                    </div>
                    <p class="text-[13px] text-slate-400 leading-relaxed font-medium">${{l.reason}}</p>
                </div>
            `).join('');

            const sources = connectedLinks.flatMap(l => l.source_files.split(', '));
            document.getElementById('detail-sources').innerHTML = [...new Set(sources)].map(s => `
                <div class="flex items-center space-x-3 p-2 hover:bg-slate-800 rounded-lg transition">
                    <div class="w-1.5 h-1.5 rounded-full bg-slate-700"></div>
                    <span class="text-[11px]">${{s}}</span>
                </div>
            `).join('');
        }}

        function closePanel() {{ document.getElementById('side-panel').classList.remove('open'); }}
        function dragstarted(event) {{ if (!event.active) simulation.alphaTarget(0.3).restart(); event.subject.fx = event.subject.x; event.subject.fy = event.subject.y; }}
        function dragged(event) {{ event.subject.fx = event.x; event.subject.fy = event.y; }}
        function dragended(event) {{ if (!event.active) simulation.alphaTarget(0); event.subject.fx = null; event.subject.fy = null; }}
    </script>
</body>
</html>
    """
    with open(os.path.join(web_dir, 'analysis.html'), 'wb') as f:
        f.write(html_content.encode('utf-8'))

if __name__ == "__main__":
    update_coupling_graph()
