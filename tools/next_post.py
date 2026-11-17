"""
Decide whether today is a posting day and, if so, what to write about.

Run from the repo root (after `git fetch origin`):
    python tools/next_post.py               # decide for today (UTC)
    python tools/next_post.py --today 2026-12-01

Prints one JSON object, e.g.
    {"post": false, "reason": "posted 1 day ago; roll 0.83 > 0.15"}
    {"post": true, "number": 7, "date": "...", "lane": "...", "domain": "...", "concept": "...", ...}

Rhythm: irregular, averaging 2-3 posts a week.
  - never twice in one day
  - never more than 3 posts in any 7-day window
  - pause if 3 or more PRs are still waiting for review (don't pile up)
  - otherwise post with a probability that rises with days since the last post
  - always post once 4 days have gone by
Topic: least-used lane (not the same lane twice running), a domain not used in
the last 2 posts that hasn't been paired with that lane yet, and a random
unused concept from that lane's bank in topics.json.
"""
import argparse
import json
import random
import subprocess
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POST_PROBABILITY = {1: 0.15, 2: 0.45, 3: 0.65}  # days since last post -> chance to post
MAX_GAP_DAYS = 4
MAX_PER_7_DAYS = 3
MAX_OPEN_PRS = 3


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def load_posts():
    """Posts merged to the working tree, plus posts on unmerged origin/post/* branches."""
    posts, open_slugs = {}, set()
    for meta in (ROOT / "posts").glob("*/meta.json"):
        m = json.loads(meta.read_text())
        posts[m["slug"]] = m
    for ref in git("for-each-ref", "--format=%(refname)", "refs/remotes/origin/post/").split():
        for path in git("ls-tree", "-r", "--name-only", ref, "posts/").split():
            if path.endswith("/meta.json"):
                m = json.loads(git("show", f"{ref}:{path}"))
                if m["slug"] not in posts:
                    posts[m["slug"]] = m
                    open_slugs.add(m["slug"])
    return sorted(posts.values(), key=lambda m: (m["date"], m["number"])), open_slugs


def decide(posts, open_slugs, today, rng):
    dates = [date.fromisoformat(p["date"]) for p in posts]
    if today in dates:
        return False, "already posted today"
    if len(open_slugs) >= MAX_OPEN_PRS:
        return False, f"{len(open_slugs)} PRs waiting for review; pausing until some are merged"
    recent = [d for d in dates if today - timedelta(days=6) <= d < today]
    if len(recent) >= MAX_PER_7_DAYS:
        return False, f"{len(recent)} posts in the last 7 days"
    if not dates:
        return True, "first post"
    gap = (today - max(dates)).days
    if gap >= MAX_GAP_DAYS:
        return True, f"{gap} days since last post"
    p, roll = POST_PROBABILITY[gap], rng.random()
    if roll < p:
        return True, f"posted {gap} day(s) ago; roll {roll:.2f} < {p}"
    return False, f"posted {gap} day(s) ago; roll {roll:.2f} >= {p}"


def pick_topic(posts, topics, rng):
    lanes, domains = topics["lanes"], topics["domains"]
    lane_count = {k: sum(p["lane"] == k for p in posts) for k in lanes}
    last_lane = posts[-1]["lane"] if posts else None
    candidates = [k for k in lanes if k != last_lane] or list(lanes)
    low = min(lane_count[k] for k in candidates)
    lane = rng.choice([k for k in candidates if lane_count[k] == low])

    recent_domains = {p["domain"] for p in posts[-2:]}
    paired = {p["domain"] for p in posts if p["lane"] == lane}
    dom_count = {k: sum(p["domain"] == k for p in posts) for k in domains}
    pool = [k for k in domains if k not in recent_domains and k not in paired] \
        or [k for k in domains if k not in recent_domains] or list(domains)
    low = min(dom_count[k] for k in pool)
    domain = rng.choice([k for k in pool if dom_count[k] == low])

    used = {p["concept"] for p in posts if p["lane"] == lane}
    bank = lanes[lane]["concepts"]
    unused = [c for c in bank if c not in used]
    concept = rng.choice(unused) if unused else None  # None -> bank exhausted, choose a new one
    return lane, domain, concept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    topics = json.loads((ROOT / "topics.json").read_text())
    posts, open_slugs = load_posts()
    ok, reason = decide(posts, open_slugs, args.today, rng)
    out = {"post": ok, "reason": reason, "open_prs": len(open_slugs)}
    if ok:
        lane, domain, concept = pick_topic(posts, topics, rng)
        out.update({
            "number": max((p["number"] for p in posts), default=0) + 1,
            "date": args.today.isoformat(),
            "lane": lane,
            "lane_label": topics["lanes"][lane]["label"],
            "domain": domain,
            "domain_label": topics["domains"][domain]["label"],
            "fictional_org": topics["domains"][domain]["fictional_org"],
            "real_data_hint": topics["domains"][domain]["real_data_hint"],
            "concept": concept or "BANK EXHAUSTED: choose a new interview-relevant concept and add it to topics.json",
            "covered_in_lane": sorted({p["concept"] for p in posts if p["lane"] == lane}),
        })
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
