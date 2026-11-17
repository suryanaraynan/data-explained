# Playbook for scheduled runs

This file is the instruction set for the scheduled Claude run that drafts case files. Each run starts with no memory, so everything it needs is here. The owner reviews and merges every PR. **Never push to `main`.**

## 0. Decide whether today is a posting day

```bash
# the clone is shallow and single-branch, so fetch the open post branches explicitly
git fetch --depth=1 --prune origin '+refs/heads/post/*:refs/remotes/origin/post/*'
pip install -q --break-system-packages -r requirements.txt
python tools/next_post.py
```

- If `"post": false`, **stop**. Report the `reason` in one line. Make no branch, commit or PR.
- If `"post": true`, use the `number`, `date`, `lane`, `domain`, `fictional_org`, `real_data_hint` and `concept` it returns. Don't overrule the picks. If `concept` says the bank is exhausted, choose a new interview-relevant concept for that lane that isn't in `covered_in_lane`, and add it to that lane's list in `topics.json` in the same PR.

## 1. Frame the problem

Write the question a real stakeholder in that domain would ask: an operations director, a store manager, a risk analyst, a council officer, an HR business partner. It should:

- name a decision that depends on the answer, and what getting it wrong would cost
- need the concept to answer it properly, so the technique isn't bolted on
- be phrased the way a non-technical person would ask it, ideally as a yes/no or "which one?" question

Use the domain's fictional organisation. Never make claims about real named organisations' internal data.

## 2. Build the data

- Generate it **in `analysis.py`** with `numpy.random.default_rng(<fixed seed>)`, so the run is reproducible.
- Make it realistic: real-world shapes (seasonality, skew, heavy tails, class imbalance) and **at least one piece of real-world mess** that the concept or a gotcha has to deal with (gaps, duplicates, late-arriving rows, schema drift, leakage, confounding).
- Label it clearly as synthetic in the docstring and in section 2 of the README.
- Point readers to a real public dataset, using `real_data_hint` as a starting point. **Verify the source exists with a web search before naming it.** Link only URLs you have opened. If unsure, name the publisher without a link.

## 3. Write the code: `posts/<date>-<slug>/analysis.py`

- Runs **offline** in under 60 seconds with only `requirements.txt`. No API keys, no network, no downloads.
- SQL lane: use DuckDB SQL over pandas DataFrames. Other lanes: pandas / scikit-learn / scipy / statsmodels.
- AI / LLM / RAG lane: implement the idea with local, deterministic tools (TF-IDF, BM25 written in a few lines, sklearn nearest neighbours, regex extraction, small hand-labelled eval sets). In the README, say exactly where a hosted LLM or embedding model would slot in, and what would change.
- Where possible, show a gotcha **in code**: compute the wrong way and the right way, and print both.
- Print every number the README will quote.
- Save **one** chart as `chart.png` (matplotlib, `dpi=150`, about 10×4.6 inches). Style:
  - surface `#fcfcfb`; text `#0b0b0b` / `#52514e`; grid `#e6e5e1`, y-axis only
  - series colours in this order: `#2a78d6`, `#eb6834`, `#1baf7a`, `#eda100`; muted context data `#c3c2bc`
  - 2px lines, no top/right/left spines, left-aligned title that states what it shows plus "(synthetic)"
  - one y-axis only; a legend for 2+ series; label the series at the line end where possible
  - if a chart doesn't help, use a results table instead and skip the PNG (drop the image line from the README)
- Run it. Fix it until it runs cleanly. Look at `chart.png` and check for overlapping labels.

## 4. Write the case file: `posts/<date>-<slug>/README.md`

Follow `posts/_template/README.md` exactly: same seven sections, same order. `posts/2026-11-17-ae-mondays-rolling-average/` is the reference example for depth and tone.

Voice and quality bar:
- **Plain English first.** If a sentence needs a technical term, explain it the first time it appears.
- **Every number comes from the actual run output.** Never estimate or round differently from the printout.
- "Explain it twice": the stakeholder version is at most 3 sentences with **zero** jargon and leads with the answer. The interviewer version names the method, the alternative rejected, and the key assumption.
- Interview drill: one concept question, one scenario question ("a stakeholder says X…"), one trade-off question. Answers of 3–5 sentences that someone could say out loud.
- Keep it to roughly 900–1,300 words. Cut anything that doesn't serve the reader.
- No hype words ("powerful", "game-changing", "dive into", "unlock"). No emojis.

## 5. Write `meta.json`

```json
{
  "number": <number>,
  "date": "<date>",
  "slug": "<date>-<short-kebab-slug>",
  "title": "<the question, as in the README H1 without 'Case file #NNN: '>",
  "lane": "<lane>",
  "domain": "<domain>",
  "concept": "<concept>",
  "summary": "<one sentence, under 120 characters>"
}
```

## 6. Open the pull request

- Branch: `post/<slug>`, created from the latest `origin/main`.
- Change **only** `posts/<slug>/`, plus `topics.json` if you added a concept. Don't edit other posts, the root README (CI rebuilds the index after merge), tools or workflows.
- Commit message: `Case file #NNN: <title>`
- PR title: `Case file #NNN: <title>`
- PR body, so the owner can review it from their phone:
  1. **30-second read**: the TL;DR
  2. **Explain it to a manager**: copied from section 5
  3. **The 3 interview questions**: questions only, as a self-test
  4. **Review checklist**: `- [ ] I can explain the method without notes`, `- [ ] Numbers match the run output`, `- [ ] Chart reads clearly`
  5. Lane / domain / concept on one line
- Push with `git -c push.negotiate=true push -u origin post/<slug>`.
- Open the PR with the **REST API** (`gh pr create` uses GraphQL, which is blocked in these sessions):
  ```bash
  gh api repos/suryanaraynan/data-explained/pulls -f title="Case file #NNN: <title>" \
     -f head="post/<slug>" -f base="main" -F body=@/tmp/pr_body.md --jq .html_url
  ```
- Report the PR URL as the final line of the run.

## Final checks before opening the PR

- [ ] `python posts/<slug>/analysis.py` runs cleanly from a fresh shell
- [ ] Every number in the README appears in the script's printed output
- [ ] Data labelled synthetic; the organisation is the fictional one from `topics.json`
- [ ] Any external link was opened and works
- [ ] All seven sections present, in order; about 900–1,300 words
- [ ] Only `posts/<slug>/` (and maybe `topics.json`) changed
