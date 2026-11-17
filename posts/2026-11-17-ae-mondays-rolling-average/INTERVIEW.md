# Interview script: Case file #001, "Is A&E demand rising, or is it just Monday?"

**Use for:** "Tell me about an analysis you're proud of" · "Describe a time you stopped a stakeholder overreacting to data" · "How do you handle messy or missing data?" · "Walk me through a SQL problem you solved" · NHS / public sector data roles

> **Framing (always):** this is a portfolio project. Say *"In a portfolio project, I modelled a scenario on NHS A&E data…"* Never present Northshire as an employer, or the synthetic data as real. Interviewers respect a well-reasoned project; they don't respect a story that falls apart under follow-up questions.

---

## The 60-second version

> "In a portfolio project, I took a common NHS situation: an operations director sees 538 A&E attendances on a Monday and asks whether to open an escalation ward.
>
> **My job** was to tell a real rise in demand apart from a normal weekly pattern, and to answer in terms of the trust's own trigger: a 7-day average above 480.
>
> **I made three key decisions.** I measured the Monday effect first. I used a 7-day rolling average, because it cancels the weekly cycle exactly. And I built it with a date-based window so a gap in the data couldn't quietly distort it.
>
> **The result:** Mondays run 14% above average in every one of 25 months. Underlying demand was up only 2.6% on last year, and it never crossed 480. Even the winter peak was 470. So my recommendation was not to open the ward, but to plan for winter and build the growth into next year's staffing.
>
> **What I took from it:** agree the decision threshold before touching the data. It turned a vague 'is it busy?' into a yes-or-no answer."

---

## The full version, about 3–4 minutes

**Signpost first:**
> "I'll cover the situation, what I set out to answer, the four decisions I made and why, the result, and what I'd do differently."

### S: Situation
> "This was a portfolio project modelled on NHS England's published A&E statistics. The scenario: a trust's operations director opens Tuesday's dashboard and sees 538 attendances on Monday, against what feels like a normal 450. They ask: *are we surging, and should we open the escalation ward?* That's expensive. It means agency staff and cancelled planned operations, so a false alarm has a real cost."

*Point to chart 1 (the 14-day dashboard bars) if you're sharing your screen.*

### T: Task
> "My task was to answer the question the director actually needed answered. That wasn't 'what happened on Monday?' but 'has underlying demand changed enough to hit our escalation trigger?' The trust's plan set that trigger at a 7-day average above 480 a day. So I set myself two things to prove or disprove: is Monday unusual, and is the underlying level rising towards 480?"

### A: Action, in four decisions

> "There were four decisions that shaped the answer."

**Decision 1: Quantify the pattern before judging the spike.**
> "First, I measured how much busier Mondays normally are: each weekday's average compared with the overall average, using a window function on top of an aggregate. Mondays came out 14.4% above average. Then I split it by month to check it wasn't a seasonal one-off. Monday was the busiest day in all 25 months."
- **Why:** you can't call a number unusual until you know what usual looks like for that same weekday.
- **Trade-off:** it adds a step before the headline answer, but it ends the "is Monday special?" debate with evidence rather than opinion.

**Decision 2: Use a 7-day rolling average as the measure of demand.**
> "Next, I needed a measure of underlying demand. I used a trailing 7-day rolling average, because any 7-day window contains exactly one of each weekday, so the Monday spike cancels out."
- **Alternatives considered:** a monthly average (too slow, and months have different weekday mixes), or comparing each Monday with the previous Monday (fine for spotting a spike, weak for the trend).
- **Trade-off:** a trailing average reacts late, about half a week behind a sudden change. I accepted that because the trigger is itself defined on a 7-day average, so I matched the measure to the decision rule. For fast detection I'd add a control chart. More on that below.

**Decision 3: Make the window date-aware, not row-aware.**
> "The data had a 4-day reporting outage in March. A standard `ROWS` window would have averaged the last 7 *rows*, which there actually covered 11 calendar days, with no warning. I used a `RANGE` window over the last 7 *days*, and counted the days in each window so partial weeks were flagged and left out."
- **Alternative considered:** filling in the missing days.
- **Why I rejected it:** filling gaps invents data on a metric that drives a spending decision. Leaving a visible gap is more honest.
- **Trade-off:** a few days have no value on the chart, which I labelled as the outage rather than hiding.

**Decision 4: Compare like with like, year on year.**
> "To check for growth, I compared each week with the same week last year, using a lag of 364 days rather than 365. That's exactly 52 weeks, so Mondays line up with Mondays. A 365-day lag would compare Mondays with Sundays and invent a big swing out of nothing."
- **Trade-off:** fixed-date holidays like Christmas drift by a day each year, so those weeks need checking by hand.

**How I communicated it (if they ask about stakeholders):**
> "I built three visuals for three questions. The first shows what the director saw, so they feel understood. The second is a heatmap proving Mondays are always the busiest. The third is the trend against last year and the 480 trigger line, so the answer is visible without reading a single number. The headline of each chart *is* the finding, not a label."

### R: Result
> "The result had three parts:
> - The latest Monday was **19% above that week's average**, close to the usual 14% uplift. It was a normal Monday, not a surge.
> - Underlying demand was **452 a day, up 2.6% on the same week last year (441)**. That's real growth, but gradual.
> - The 7-day average **never crossed 480** in two years. The highest point was **470 on 15 February**, at the peak of winter.
>
> **The recommendation:** don't open the escalation ward on the strength of one Monday. Plan escalation capacity for December to February, when the weekly level genuinely climbs. And build about 2–3% annual growth into next year's staffing model."

### Reflection: what I learned and what I'd do differently
> "Three reflections:
> 1. **The most valuable step wasn't technical.** It was pinning the question to the trust's own trigger. Without it, I'd have answered 'is it busy?', which can't be acted on.
> 2. **Silent errors matter more than loud ones.** The `ROWS` vs `RANGE` issue doesn't error, and it doesn't look wrong on a chart. Now, with any time series, I check for gaps and count the days in every window.
> 3. **With real trust data, I'd extend it:** treat bank holidays separately, since the Tuesday after a bank holiday Monday behaves like a Monday; split walk-ins from ambulance arrivals; and replace the fixed trigger check with a forecast with prediction intervals, so the director gets an early warning *before* the average reaches 480, not after."

---

## Decision log: the whole case on one page

| # | Decision | Why | Alternative rejected | Trade-off accepted |
|---|---|---|---|---|
| 0 | Frame the question as "will we hit the 480 trigger?" | Turns a vague worry into a yes/no decision | "Analyse A&E demand" | Narrower scope |
| 1 | Measure the weekday effect first (and by month) | You can't call a spike unusual without knowing normal | Judge Monday against the overall average | One extra step before the answer |
| 2 | Trailing 7-day rolling average | Cancels the weekly cycle exactly; matches the trigger's definition | Monthly average; Monday vs last Monday | Reacts about 3 days late to sudden change |
| 3 | `RANGE` window plus day count | Data gaps silently break `ROWS` windows | Fill in the missing days | Visible gaps on the chart |
| 4 | 364-day lag for year on year | Keeps weekdays aligned | 365-day lag | Fixed-date holidays drift a day |
| 5 | Three visuals, each headlined with its finding | Non-technical readers get the answer at a glance | One dense chart | More visuals to maintain |

**Numbers to remember:** Monday **+14.4%** on average · busiest day in **25 of 25** months · latest Monday **538 (+19%)** · 7-day average **452 vs 441 (+2.6%)** · winter peak **470** (15 Feb) · trigger **480**, never crossed.

---

## Likely follow-up questions

**"Why not just compare this Monday with last Monday?"**
> "That's a good check for spotting a spike, and I'd show it. But one Monday against one Monday is noisy: both are single days. The decision is about the underlying level, and the trigger is defined on a 7-day average, so I used the measure the decision is based on."

**"The director still wants to open the ward. What do you do?"**
> "I'd make sure I understood what they were seeing that I wasn't, such as staffing gaps or bed occupancy, because demand is only one input. Then I'd show the trend against the trigger and agree a clear rule: if the 7-day average goes above, say, 470 for three days running, we revisit. That respects their judgement and keeps the decision tied to data."

**"How would you automate this?"**
> "A daily scheduled query that calculates the 7-day average with the `RANGE` window, flags partial windows, and alerts at two levels: an early warning when the forecast says the average will cross 480 within 7 days, and an alert when it actually crosses. In Fabric or Databricks, that's a scheduled notebook or pipeline feeding a Power BI tile."

**"How would you check this on real data?"**
> "Backtest it. Take past winters, run the same logic day by day as if live, and check whether it would have flagged the real escalation periods early enough, and how many false alarms it would have raised."

**"What would make your conclusion wrong?"**
> "If the growth were concentrated in the most serious cases, flat total attendances could hide rising pressure. So with real data I'd also look at the case mix, admissions and four-hour performance, not just counts."

---

## Saying it well
- **Lead with the answer for non-technical panels:** "It was a normal Monday. Demand is up 2.6%, below the trigger." Then the reasons.
- **For technical panels**, slow down on Decisions 3 and 4. That's where the depth shows.
- **Use the signposts out loud:** "There were four decisions… The first… The trade-off there was… So the result…" They help the panel follow and take notes.
- **Never apologise for it being a portfolio project.** Say what you would do with real data. That's the senior-level answer.
