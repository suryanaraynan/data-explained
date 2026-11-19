# Interview script: Case file #002, "Is our Saver Nights tariff cutting peak electricity use, or making it worse?"

**Use for:** "Tell me about a data model you designed" · "Describe a time you found a number on a dashboard was wrong" · "How do you make sure a pipeline's output is correct?" · "Explain a star schema to a non-technical person" · energy, utilities and data engineering roles

> **Framing (always):** this is a portfolio project. Say *"In a portfolio project, I modelled a scenario on UK half-hourly smart meter data, like UK Power Networks' Low Carbon London dataset…"* Never present Brightwater Energy as an employer, or the synthetic data as real.

---

## The 60-second version

> "In a portfolio project, I took an energy supplier scenario: the tariff dashboard said customers on a time-of-use tariff, Saver Nights, were using 33.3% more electricity at peak, and the commercial director was asking whether to close the trial.
>
> **My job** was to find out whether that number was real, and to answer against the trial's target: at least 10% less peak use than flat-rate homes.
>
> **I made three key decisions.** I declared the grain first, one row per meter per half-hour, which showed the dashboard's join was double-counting. I built a star schema where each reading carries the tariff in force that day, not today's tariff. And I added placeholder customer rows, so meters the CRM hadn't caught up with weren't silently dropped.
>
> **The result:** the flat query overstated total electricity by 48.2%. In the star schema, Saver Nights homes use 19.1% less at peak, in all 6 regions. So my recommendation was to keep the trial and retire the flat query.
>
> **What I took from it:** reconcile to the source before you trust any total."

---

## The full version, about 3–4 minutes

**Signpost first:**
> "I'll cover the situation, what I set out to answer, the four decisions I made and why, the result, and what I'd do differently."

### S: Situation
> "This was a portfolio project modelled on UK half-hourly smart meter data. The scenario: a fictional supplier, Brightwater Energy, is trialling Saver Nights, a tariff that makes 4pm to 7pm expensive and nights cheap. The dashboard shows Saver Nights homes using 3.68 kWh at peak per day, against 2.76 on the standard tariff: 33.3% *more*. The commercial director is asking whether to close the trial before winter. Closing a tariff that works throws away the peak savings; expanding one that doesn't makes peak demand worse."

*Point to chart 1 (the dashboard bars against the 10% target line) if you're sharing your screen.*

### T: Task
> "My task was to answer one question the director could act on: do Saver Nights homes use at least 10% less electricity at peak than flat-rate homes? Before answering it, I needed to know whether the dashboard number could be trusted at all, because the result went against everything time-of-use tariffs are designed to do."

### A: Action, in four decisions
> "There were four decisions that shaped the answer."

**Decision 1: Declare the grain and reconcile before analysing.**
> "First, I wrote down what one row of the data should mean: one meter reading per half-hour. Then I counted rows and summed electricity at every step from the meter feed to the dashboard. The meter feed had 3,252,480 rows. The dashboard query had 4,838,400, with 1,612,800 duplicates. It joined readings to tariff history on account only, so every reading was repeated once per tariff the customer had ever had."
- **Why:** a surprising result is more often a data problem than a real effect, and a reconciliation finds the step where it goes wrong.
- **Alternative considered:** analysing the dashboard numbers as given.
- **Trade-off:** time spent on plumbing before any insight, but it changed the answer from "close it" to "keep it".

**Decision 2: Build a star schema, not a patched query.**
> "I could have fixed the one join. Instead I built a star schema: a fact table at the meter × half-hour grain, with date, time-of-day, customer and tariff dimensions. Peak time lives in one place, as a flag on the time dimension."
- **Why:** the same mistake would be made by the next person writing a query. A model with agreed definitions prevents it for everyone.
- **Alternative considered:** a `DISTINCT` or a corrected join in the dashboard query.
- **Trade-off:** more upfront work and more tables to maintain, which pays off once more than one report uses the data.

**Decision 3: Resolve the tariff "as at" the reading.**
> "Each reading picks up the tariff that was in force on that day, using the valid-from and valid-to dates. Grouping by the customer's *current* tariff had put switchers' earlier usage under Saver Nights. That was 18.0% of that group's electricity."
- **Why:** the question is about behaviour on the tariff, so the label has to be true at the time.
- **Alternative considered:** grouping by current tariff, which is simpler and what the dashboard did.
- **Trade-off:** a date-range join at load time is slower than a plain key join, but it runs once, not in every report.

**Decision 4: Placeholder rows for meters the CRM hadn't caught up with (data quality).**
> "40 new meters were sending readings before their customer records loaded. An inner join dropped them: 0.9% of the electricity. I added a placeholder row to the customer dimension for each one, so their readings stay in the fact table and get filled in when the CRM catches up."
- **Why:** facts should never disappear because a description is late.
- **Alternative considered:** dropping them, or loading them with a null customer key.
- **Trade-off:** placeholders have to be monitored and replaced, so I flag them with `is_placeholder`.

**How I communicated it:**
> "Three visuals. The first is the dashboard the director saw, so the starting point is shared. The second is the reconciliation table, which shows exactly where the extra 48.2% came from, with no SQL. The third is the average day for each tariff with the peak shaded, so the answer is visible at a glance. For the director, I said it in three sentences with no jargon; for the data team, I gave the grain, the join and the tests."

### R: Result
> "The result had three parts:
> - The dashboard query overstated total electricity by **48.2%**, 931.7 MWh against 628.5 MWh metered. The star schema with placeholders matched the feed exactly.
> - Saver Nights homes use **1.78 kWh at peak per day against 2.20** for flat-rate homes: **19.1% less**. Their total is about the same, because use moves to the night, up 17.1%.
> - It holds in **all 6 regions**, and the 150 mid-trial switchers went from **−0.8%** against flat-rate homes before switching to **−21.9%** after.
>
> **The recommendation:** keep the trial and plan the roll-out. Retire the flat query, and add a daily check that the fact table reconciles to the meter feed."

### Reflection: what I learned and what I'd do differently
> "Three reflections:
> 1. **When a result contradicts how the thing is designed to work, check the plumbing first.** The director's question was really 'can I trust this number?' before it was 'is the tariff working?'.
> 2. **The dangerous bugs don't error.** A fan-out and an inner join both run fine and produce plausible numbers. Grain tests and reconciliation are what catch them, so they belong in the pipeline, not in a one-off check.
> 3. **With real data I'd extend it:** handle clock-change days, which have 46 or 50 half-hours; deal with people choosing the tariff themselves, since flexible households are more likely to sign up, by leaning on the before/after comparison or a randomised offer; and run the load incrementally with the grain and reconciliation tests as gates in the pipeline."

---

## Decision log: the whole case on one page

| # | Decision | Why | Alternative rejected | Trade-off accepted |
|---|---|---|---|---|
| 0 | Frame it as "at least 10% less peak use than flat-rate homes?" | Gives the director a yes/no tied to the business case | "Analyse tariff usage" | Narrower scope |
| 1 | Declare the grain and reconcile every stage to the meter feed | Finds where the numbers go wrong | Take the dashboard at face value | Plumbing before insight |
| 2 | Star schema with a shared `is_peak` flag | One definition for everyone | Patch the one query with `DISTINCT` | More tables to maintain |
| 3 | Tariff resolved "as at" the reading | Labels must be true at the time | Group by current tariff | Slower date-range join at load |
| 4 | Placeholder customer rows for unknown meters | Facts never go missing | Inner join (drop) or null keys | Placeholders to monitor and replace |
| 5 | Three visuals, including a reconciliation table | Non-technical readers see where the error came from | One results chart | More to explain |

**Numbers to remember:** dashboard **+33.3%** · flat query **+48.2%** electricity, **1,612,800** duplicates · star: **1.78 vs 2.20 kWh** at peak, **−19.1%** · **6 of 6** regions · switchers **−0.8% → −21.9%** · **40** placeholder meters, **0.9%** of kWh.

---

## Likely follow-up questions

**"Why not just fix the join in the dashboard?"**
> "That fixes one report today. The tariff history table would still be there for the next analyst to join the same way. Putting the date-range join in the load, once, and testing the grain means every report built on the model is right by default."

**"The director still wants to close the trial. What do you do?"**
> "I'd ask what else is worrying them, such as customer complaints or bill shock, because peak use is only one input. Then I'd show the reconciliation table, since that explains why the old number was wrong without any SQL, and the before/after for the switchers, which is the hardest result to argue with."

**"How would you productionise this?"**
> "An incremental daily load: append the new half-hours to the fact table, resolve keys as at the reading, add placeholders for unknown meters, and replace them when the CRM catches up. Two gates before the report refreshes: a grain uniqueness test and a reconciliation to the meter feed. In Fabric or Databricks that's a scheduled pipeline with the tests as a quality step."

**"How would you validate it on real data?"**
> "Reconcile monthly totals to settlement or billing figures, spot-check a few households by hand from raw readings to the report, and compare the tariff effect with the published Low Carbon London trial, where around 1,100 homes were on a time-of-use tariff."

**"What would make your conclusion wrong?"**
> "Self-selection. If flexible households chose the tariff, they'd look better than flat-rate homes whatever the tariff did. That's why the within-household before/after for switchers matters: they ran about the same as flat-rate homes before switching and 21.9% lower after."

---

## Saying it well
- **Lead with the answer for non-technical panels:** "The tariff works: 19.1% less at peak. The dashboard was double-counting." Then the why.
- **For data engineering panels**, slow down on the grain and the "as at" join. Draw the star on a whiteboard if you can.
- **Show chart 2 (the reconciliation table) when they ask about data quality.** It's the most convincing single picture in the case.
- **Never apologise for it being a portfolio project.** Talk about what you would do with real data and in production.
