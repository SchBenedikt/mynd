import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.decomposition import PCA

chunks = json.loads(Path("data/chunks.json").read_text())
embs = np.load("data/embeddings.npy")

doc_chunks = defaultdict(list)
for c, e in zip(chunks, embs):
    doc_chunks[c["source"]].append(e)
docs = list(doc_chunks.keys())
doc_embs = np.array([np.mean(doc_chunks[d], axis=0) for d in docs])
n = len(docs)
print(f"{n} Dokumente")

normed = doc_embs / np.linalg.norm(doc_embs, axis=1, keepdims=True)
sim = normed @ normed.T

edges = []
for i in range(n):
    s = sim[i].copy()
    s[i] = 0
    candidates = np.where(s > 0.35)[0]
    top = candidates[np.argsort(-s[candidates])[:5]]
    for j in top:
        if i < j:
            edges.append([int(i), int(j), float(s[j])])
print(f"{len(edges)} Kanten")

pca = PCA(n_components=2, random_state=42)
coords = pca.fit_transform(doc_embs)

def fkey(p, d=2):
    parts = p.split("/")
    return "/".join(parts[:d]) if len(parts) >= d else parts[0]

folders = [fkey(d) for d in docs]
topf = [f for f, _ in Counter(folders).most_common(30)]
fcl = ["#e6194b","#3cb44b","#ffe119","#4363d8","#f58231","#911eb4","#42d4f4","#f032e6","#bfef45","#fabed4",
       "#469990","#dcbeff","#9a6324","#fffac8","#800000","#aaffc3","#808000","#ffd8b1","#000075","#a9a9a9",
       "#e6beff","#46f0f0","#f0a0a0","#a0f0a0","#f0e68c","#ffb347","#87ceeb","#dda0dd","#98fb98","#ffd700"]
fm = {f: fcl[i] for i, f in enumerate(topf)}

s = 60
node_data = []
for i, doc in enumerate(docs):
    node_data.append({
        "id": i, "name": doc.split("/")[-1], "path": doc,
        "x": float(coords[i,0]*s), "y": float(coords[i,1]*s),
        "r": max(3, min(10, np.sqrt(len(doc_chunks[docs[i]]))*2)),
        "c": fm.get(folders[i], "#a9a9a9"),
        "size": len(doc_chunks[docs[i]])
    })

edge_data = [{"s": i, "t": j, "w": w} for i, j, w in edges]

html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* {{ margin:0; padding:0; }}
body {{ background:#0d1117; overflow:hidden; font-family:system-ui,sans-serif; }}
#header {{ position:fixed; top:0; left:0; right:0; z-index:10;
  background:linear-gradient(180deg,#0d1117 80%,transparent);
  padding:12px 20px 8px; }}
h1 {{ display:inline; font-size:16px; font-weight:300; color:#f0f6fc; }}
#stats {{ display:inline; margin-left:12px; font-size:11px; color:#8b949e; }}
#stats strong {{ color:#e6edf3; }}
svg {{ display:block; }}
#tip {{ position:fixed; display:none; background:#161b22; border:1px solid #30363d;
  border-radius:6px; padding:8px 12px; font-size:11px; color:#e6edf3; pointer-events:none; z-index:20;
  box-shadow:0 4px 12px rgba(0,0,0,.4); }}
</style></head><body>
<div id="header">
  <h1>Dokumenten-Netzwerk</h1>
  <span id="stats"><strong>{n:,}</strong> Dokumente · <strong>{len(edges):,}</strong> Verbindungen</span>
</div>
<div id="tip"></div>
<script>
const nodes = {json.dumps(node_data)};
const links = {json.dumps(edge_data)};

const w = window.innerWidth, h = window.innerHeight;
const svg = d3.select("body").append("svg").attr("width",w).attr("height",h);
const g = svg.append("g");

const zoom = d3.zoom().scaleExtent([0.05,40]).on("zoom", e => g.attr("transform", e.transform));
svg.call(zoom);

// Kanten
g.append("g").selectAll("line").data(links).join("line")
  .attr("x1", d => nodes[d.s].x).attr("y1", d => nodes[d.s].y)
  .attr("x2", d => nodes[d.t].x).attr("y2", d => nodes[d.t].y)
  .attr("stroke", "#58a6ff")
  .attr("stroke-opacity", d => Math.max(0.12, d.w * 0.6))
  .attr("stroke-width", d => Math.max(0.5, d.w * 3.5))
  .attr("stroke-linecap", "round");

// Knoten
const circles = g.append("g").selectAll("circle").data(nodes).join("circle")
  .attr("cx", d => d.x).attr("cy", d => d.y)
  .attr("r", d => d.r).attr("fill", d => d.c)
  .attr("opacity", 0.8).attr("stroke", "none")
  .on("mouseover", function(e, d) {{
    d3.select(this).attr("opacity",1).attr("stroke","#fff").attr("stroke-width",1.5);
    const conn = links.filter(l => l.s===d.id || l.t===d.id);
    conn.forEach(l => {{
      const ni = l.s===d.id ? l.t : l.s;
      d3.select(circles.nodes()[ni]).attr("opacity",1).attr("stroke","#fff").attr("stroke-width",1.5);
    }});
    d3.select("#tip").style("display","block")
      .html(`<b>${{d.name}}</b><br><small>${{d.path}}</small><br>${{d.size}} Chunks · ${{conn.length}} Verbindungen`)
      .style("left",(e.pageX+14)+"px").style("top",(e.pageY-8)+"px");
  }})
  .on("mouseout", function() {{
    d3.select(this).attr("opacity",.8).attr("stroke","none");
    circles.attr("opacity",.8).attr("stroke","none");
    d3.select("#tip").style("display","none");
  }});

// Zentrieren
const cx = d3.mean(nodes, d => d.x);
const cy = d3.mean(nodes, d => d.y);
const maxR = d3.max(nodes, d => Math.hypot(d.x-cx, d.y-cy));
const scale = Math.min(w, h) / (maxR * 2.5);
svg.call(zoom.transform, d3.zoomIdentity.translate(w/2 - cx*scale, h/2 - cy*scale).scale(scale));
</script></body></html>
'''

with open("data/viz.html", "w") as f:
    f.write(html)
print(f"✅ data/viz.html ({Path('data/viz.html').stat().st_size/1024:.0f} KB)")
