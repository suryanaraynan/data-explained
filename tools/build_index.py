"""
Rebuild the case-file index in the root README.md from posts/*/meta.json.
Runs automatically on every push to main (.github/workflows/index.yml).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START, END = "<!-- INDEX:START -->", "<!-- INDEX:END -->"

topics = json.loads((ROOT / "topics.json").read_text())
posts = sorted(
    (json.loads(p.read_text()) for p in (ROOT / "posts").glob("*/meta.json")),
    key=lambda m: m["number"],
    reverse=True,
)

lines = [f"**{len(posts)} case file{'' if len(posts) == 1 else 's'}** · "
         + " · ".join(f"{v['label']}: {sum(p['lane'] == k for p in posts)}"
                      for k, v in topics["lanes"].items()),
         "",
         "**Preparing for a specific interview?** Each prep page lists every case file and interview question for that role: "
         + " · ".join(f"[{v}](https://github.com/suryanaraynan/data-interview-questions/blob/main/prep/{k}.md)"
                      for k, v in topics.get("tracks", {}).items()),
         "",
         "| # | Case file | Tracks | Domain | Concept |",
         "|---:|---|---|---|---|"]
for p in posts:
    lane = topics["lanes"].get(p["lane"], {}).get("label", p["lane"])
    dom = topics["domains"].get(p["domain"], {}).get("label", p["domain"])
    concept = p["concept"].replace("-", " ")
    short = {"data-analyst": "DA", "data-scientist": "DS", "data-engineer": "DE", "ml-engineer": "ML", "statistics": "Stats"}
    tracks = " ".join(f"`{short.get(t, t)}`" for t in p.get("tracks", [])) or lane
    lines.append(f"| {p['number']:03d} | [{p['title']}](posts/{p['slug']}/) | {tracks} | {dom} | {concept} |")

readme = ROOT / "README.md"
text = readme.read_text()
head, rest = text.split(START, 1)
_, tail = rest.split(END, 1)
readme.write_text(f"{head}{START}\n" + "\n".join(lines) + f"\n{END}{tail}")
print(f"Index rebuilt: {len(posts)} posts")
