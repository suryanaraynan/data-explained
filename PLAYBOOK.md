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
- Produce the visuals described in section 3a below.
- Run it. Fix it until it runs cleanly.

## 3a. Visuals: 2–3 per case file, report-grade

Each case file has **2 or 3 visuals**, named `chart_1.png`, `chart_2.png`, `chart_3.png` in the order they appear in the README. They must look like they came from a real analytics team's monthly pack or an operational dashboard, not a textbook plot. A visual can be a chart or a styled table.

**Where they go:**
1. **Context (required), in section 1 or 2.** Show what the stakeholder saw that triggered the question: the dashboard number that worried them, the complaint trend, the raw messy data, the funnel that looks broken. The reader should *feel* the problem before any method appears.
2. **Results (required), in section 4.** The visual that answers the question and drives the decision.
3. **Explainer (optional), wherever it helps most.** Usually section 3 (how the method works, e.g. the pattern it removes or the before/after of a fix) or section 6 (a gotcha shown visually, e.g. wrong vs right).

**Use `tools/viz_style.py` for every visual** (import it as the reference post does). It provides the palette, `figure`, `headline`, `footer`, `callout`, `ref_line`, `shade`, `end_label`, `SEQ_CMAP` / `DIV_CMAP` for heatmaps, and `table_png` for report tables.

**Every visual must have:**
1. **A headline that states the finding** as a sentence ("Mondays run 14% above average in every month"), never a label ("Attendances by weekday").
2. **A subtitle** saying what is plotted, the units and the period.
3. **A focus and a context.** The data the story is about is in colour (`SERIES[0]` first); everything else is `MUTED`.
4. **At least one annotation** on a number the README quotes (`callout`), plus real-world context where it exists: a target or threshold (`ref_line`), a benchmark or last year's line, a shaded period such as winter, an outage, a campaign or a policy change (`shade`).
5. **A footer** with "Synthetic data modelled on <source> | Data Explained #NNN".
6. One y-axis only; direct labels at line ends; a legend only when direct labels won't fit.

**Choose the form by the job the visual does**, and vary it across posts. Don't default to a line chart:

| Job | Realistic form |
|---|---|
| Trend vs target / last year | Annotated line with a target line, last year in muted dashes, events shaded |
| Pattern across two dimensions (weekday × month, hour × day, region × product) | Heatmap with `SEQ_CMAP` (or `DIV_CMAP` for above/below a midpoint), cell values when there's room |
| Ranking / comparison across groups | Sorted horizontal bars, the focus group highlighted, benchmark line |
| Before vs after, or two points per group | Dumbbell / slope chart |
| Distribution or spread | Histogram or box/strip plot with median and target marked |
| Change in a total (bridges, waterfalls) | Waterfall |
| Funnel / pipeline stages | Horizontal funnel bars with conversion % between stages |
| Many groups over time | Small multiples (shared y-axis) rather than a spaghetti chart |
| Model results | Confusion matrix heatmap, calibration curve, SHAP-style bar of feature impact, precision–recall curve with the chosen threshold marked |
| Pipeline / RAG / data-engineering posts | A results table (`table_png`): row counts per stage, latency/cost per option, recall@k per method, before/after data-quality checks. Highlight the recommended row |

Make each visual a **different form** answering a different question. Never show the same data twice in two styles.

**Before finishing:** open each PNG and look at it. Check that no labels overlap, nothing is clipped, the headline matches the numbers, and it's readable at GitHub's README width. Fix and re-render until it's clean.

## 4. Write the case file: `posts/<date>-<slug>/README.md`

Follow `posts/_template/README.md` exactly: same seven sections, same order. `posts/2026-11-17-ae-mondays-rolling-average/` is the reference example for depth and tone.

Voice and quality bar:
- **Plain English first.** If a sentence needs a technical term, explain it the first time it appears.
- **Every number comes from the actual run output.** Never estimate or round differently from the printout.
- "Explain it twice": the stakeholder version is at most 3 sentences with **zero** jargon and leads with the answer. The interviewer version names the method, the alternative rejected, and the key assumption.
- Interview drill: one concept question, one scenario question ("a stakeholder says X…"), one trade-off question. Answers of 3–5 sentences that someone could say out loud.
- Keep it to roughly 900–1,300 words. Cut anything that doesn't serve the reader.
- No hype words ("powerful", "game-changing", "dive into", "unlock"). No emojis.

## 4a. Write the interview script: `posts/<date>-<slug>/INTERVIEW.md`

Follow `posts/_template/INTERVIEW.md` exactly. `posts/2026-11-17-ae-mondays-rolling-average/INTERVIEW.md` is the reference example. This is Surya's script for walking an interviewer through the case in signposted STAR form.

- **Framing is non-negotiable:** always "a portfolio project I built", modelled on a real source. Never present the fictional organisation as an employer, or the synthetic data as real.
- Write it **in the first person, as spoken English**: short sentences, signposts said out loud ("There were three decisions… The first… The trade-off there was… So the result…").
- Include both versions: a **60-second** one (about 150 words) and a **3–4 minute** full STAR one.
- **Action = 3–5 decisions**, each with *what, why, alternative rejected, trade-off accepted*. At least one decision must be about data quality and one about communication (visuals, explaining it twice).
- **Result** uses only numbers from the run output, ending with the recommendation.
- **Reflection** has three points: a transferable learning about framing or stakeholders, a technical learning, and what you'd extend with real data (the limits of the synthetic data, and the next step to production).
- **Decision log table**, plus a one-line "Numbers to remember".
- **4–5 likely follow-up questions** with spoken answers, including "why not the simpler option?", "the stakeholder disagrees", "how would you productionise it?", "how would you validate it?" and "what would make you wrong?".

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
- The post folder must contain `README.md`, `INTERVIEW.md`, `analysis.py`, `meta.json` and the chart PNGs.
- Change **only** `posts/<slug>/`, plus `topics.json` if you added a concept. Don't edit other posts, the root README (CI rebuilds the index after merge), tools or workflows.
- Commit message: `Case file #NNN: <title>`
- PR title: `Case file #NNN: <title>`
- PR body, so the owner can review it from their phone:
  1. **30-second read**: the TL;DR
  2. **Explain it to a manager**: copied from section 5
  3. **The 3 interview questions**: questions only, as a self-test
  4. **Interview script**: the 60-second version from INTERVIEW.md, plus a link to the full file
  5. **Review checklist**: `- [ ] I can tell the 60-second version without notes`, `- [ ] I can defend every trade-off in the decision log`, `- [ ] I can explain the method without notes`, `- [ ] Numbers match the run output`, `- [ ] Chart reads clearly`
  6. Lane / domain / concept on one line
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
- [ ] 2–3 visuals (context in section 1/2, results in section 4, optional explainer), each with a finding-as-headline, subtitle, annotation and footer, checked by eye
- [ ] Data labelled synthetic; the organisation is the fictional one from `topics.json`
- [ ] Any external link was opened and works
- [ ] All seven sections present, in order; about 900–1,300 words (excluding alt text)
- [ ] INTERVIEW.md follows the template: portfolio framing, 60-second version, full STAR, 3–5 decisions with trade-offs, decision log, follow-ups
- [ ] Only `posts/<slug>/` (and maybe `topics.json`) changed
