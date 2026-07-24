import json
import statistics
from collections import Counter
from pathlib import Path

import numpy as np

chunks = json.loads(Path("data/chunks.json").read_text())
total_before = len(chunks)

bad = [i for i,c in enumerate(chunks) if "/node_modules/" in c["source"] or "/.pnpm/" in c["source"]]
keep = [c for i,c in enumerate(chunks) if i not in set(bad)]

print(f"Chunks: {len(keep):,} von {total_before:,} ({(len(bad)/total_before*100):.1f}% node_modules entfernt)")
Path("data/chunks.json").write_text(json.dumps(keep, indent=2))

embs = np.load("data/embeddings.npy")
embs_clean = np.delete(embs, bad, axis=0)
print(f"Embeddings: {embs_clean.shape[0]:,} von {embs.shape[0]:,}")
np.save("data/embeddings.npy", embs_clean)

state = json.loads(Path("data/state.json").read_text())
state_clean = {k:v for k,v in state.items() if "/node_modules/" not in k and "/.pnpm/" not in k}
print(f"Dateien: {len(state_clean):,} von {len(state):,}")
Path("data/state.json").write_text(json.dumps(state_clean, indent=2))

# ── Visualisierung ──
total = len(keep)
priv = sum(1 for c in keep if c["source"].startswith("Privat"))
get = total - priv

exts = Counter()
folders = Counter()
text_lens = []
for c in keep:
    s = c["source"]
    exts[s.rpartition(".")[2].lower()] += 1
    folder = "/".join(s.split("/")[:-1])
    folders[folder] += 1
    text_lens.append(len(c["text"]))

total_chars = sum(text_lens)
chunks_mb = Path("data/chunks.json").stat().st_size / 1024 / 1024
embs_mb = Path("data/embeddings.npy").stat().st_size / 1024 / 1024

print(f"""
{'='*55}
  VISUALISIERUNG  –  Index nach Bereinigung
{'='*55}

  Bereich:
     Privat  {priv:>5} ({priv/total*100:5.1f}%)
     Geteilt {get:>5} ({get/total*100:5.1f}%)
     Summe   {total:>5}

  Dateitypen ({total:,} Chunks):
""")

for ext, count in exts.most_common():
    bar = "█" * int(count / total * 40) + "░" * (40 - int(count / total * 40))
    print(f"    .{ext:<8} {bar} {count:>6,} ({count/total*100:5.1f}%)")

print(f"""
  Datenvolumen:
    chunks.json:      {chunks_mb:.1f} MB
    embeddings.npy:   {embs_mb:.1f} MB
    state.json:       {Path('data/state.json').stat().st_size/1024:.0f} KB

  Chunk-Statistik:
    Text gesamt:  {total_chars:,} Zeichen
    Mittelwert:   {statistics.mean(text_lens):,.0f} Zeichen
    Median:       {statistics.median(text_lens):,.0f} Zeichen

  20 größte Ordner:
""")

for folder, count in folders.most_common(20):
    pct = count / total * 100
    bar = "█" * int(pct) + "░" * max(0, 30 - int(pct))
    short = folder[:58]
    print(f"    {short:<60} {bar} {count:>5,} ({pct:4.1f}%)")

# ── Übersicht größte Quelldateien nach Chunk-Count ──
source_counts = Counter(c["source"] for c in keep)
print("\n  Top 10 Dateien (meiste Chunks):\n")
for src, cnt in source_counts.most_common(10):
    print(f"    {cnt:>5} Chunks  {src[:70]}")
