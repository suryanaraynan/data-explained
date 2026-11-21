# Interview script: Case file #003, "The new model says 18.8% of applicants will default. Do we tighten lending, or is the model wrong?"

**Use for:** "Tell me about a model you evaluated or improved" · "How do you know a model's output can be trusted?" · "Describe a time the data contradicted what a stakeholder believed" · "Explain a technical concept to a non-technical person" · banking, credit risk and insurance data science roles

> **Framing (always):** this is a portfolio project. Say *"In a portfolio project, I modelled a credit-risk scenario on UK personal lending and public credit-default data…"* Never present Thamesgate as an employer, or the synthetic data as real.

---

## The 60-second version

> "In a portfolio project, I took a credit-risk situation: a new default model tells a building society's credit committee that this quarter's applicants have an 18.8% chance of defaulting, against a board limit of 4.5%.
>
> **My job** was to decide whether the committee should tighten lending, or whether the model's percentages were wrong.
>
> **I made three key decisions.** I tested calibration, not just AUC, on an out-of-time set of loans with known outcomes. I calibrated only on mature loans, because recent loans haven't had time to default. And I chose Platt scaling over isotonic and a simple prior correction, because it was the most accurate and stable and it picks up drift.
>
> **The result:** the model ranked risk well, AUC 0.815, but over-stated it 5.0 times, because it was trained on a sample with defaults boosted to 25%. After calibration, applicants came out at 4.1%, inside appetite. So I recommended not tightening, and calibrating the model before its numbers touch pricing or provisions.
>
> **What I took from it:** a good AUC tells you nothing about whether the percentages are right."

---

## The full version, about 3–4 minutes

**Signpost first:**
> "I'll cover the situation, what I set out to answer, the four decisions I made and why, the result, and what I'd do differently."

### S: Situation
> "This was a portfolio project modelled on UK unsecured lending, with synthetic data shaped like public credit-default datasets. The scenario: a fictional building society has just put a new default model live for personal loans. Its first report says the average applicant has an 18.8% chance of defaulting in 12 months. The board's risk appetite is 4.5%, and no quarter since 2023 has gone above 4.3%. The Head of Credit Risk has to tell credit committee whether to tighten lending. Tightening on those numbers would decline 31.9% of applicants, so a false alarm costs a lot of good business."

*Point to chart 1 (quarterly default rates between 2.69% and 4.26% next to the model's 18.8% bar) if you're sharing your screen.*

### T: Task
> "My task was to answer one question: can the model's percentages be taken at face value? If yes, the committee should tighten. If not, I needed to correct them and say what the real figure was against the 4.5% limit. I judged success on loans with known outcomes: does predicted risk match actual risk, and does expected loss match realised loss?"

### A: Action, in four decisions
> "There were four decisions that shaped the answer."

**Decision 1: Test calibration, not just ranking.**
> "First, I separated two questions: does the model rank applicants correctly, and are its percentages right? AUC only answers the first. So I built a reliability curve: split test loans into ten groups by predicted risk and compare predicted with actual default rate in each."
- **Why:** pricing, provisions and risk appetite all use the percentage itself, not just the order.
- **Alternative considered:** relying on the AUC from model validation, which was a healthy 0.815.
- **Trade-off:** one more metric to explain, but it was the one that exposed the problem: calibration error of 15.07 points.

**Decision 2: Split by time and use only mature loans (data quality).**
> "Next, the data. I trained on 2023–2024, calibrated on the first half of 2025 and tested on July to October 2025: the latest loans with a full 12 months of outcome. Loans drawn after that look safer only because they haven't had time to default."
- **Why:** calibration is about absolute levels, so incomplete outcomes bias it directly.
- **Alternative considered:** calibrating on the most recent six months to capture current conditions. I tested it: it under-predicted, 3.41% against 3.79% actual, which means under-provisioning.
- **Trade-off:** the calibration window is more than a year old by the time it's used, so it can lag a fast-moving economy. I'd refit it every quarter as new loans mature.

**Decision 3: Platt scaling over the alternatives.**
> "Then I compared three fixes. A prior correction, which mathematically undoes the rebalancing. Platt scaling, a two-parameter logistic fit from score to outcome. And isotonic regression, a flexible stepwise fit."
- **Why Platt:** lowest calibration error at 0.38 points, AUC unchanged, and stable with 578 defaults to learn from.
- **Alternatives rejected:** the prior correction can't see drift since training; it predicted 3.42% against 3.79%. Isotonic was similar on the full set but overfitted badly on a 1,500-loan sample: 0.90 points against Platt's 0.48.
- **Trade-off:** Platt came out 10% above realised loss in money terms, while the prior correction was 5% below. I accepted erring on the cautious side for provisioning.

**Decision 4: Answer in the committee's terms (communication).**
> "Finally, I translated it into what the committee decides on: the average PD against the 4.5% appetite, how many applicants each version would decline, and expected loss in pounds against what actually happened."
- **Why:** "calibration error" means nothing to a credit committee; "£13.37m predicted, £2.61m happened" does.
- **Trade-off:** less technical detail on the slide, which I kept for the appendix.

**How I communicated it:**
> "Three visuals for three questions. The first shows what the committee saw: a model prediction nowhere near the history. The second is the reliability curve, showing the raw model below the diagonal and the calibrated one on it. The third is a table of the options with AUC, calibration error and expected loss, so you see at a glance that the ranking never changed but the money did."

### R: Result
> "The result had three parts:
> - The raw model over-stated risk 5.0 times: 18.86% predicted against 3.79% actual on the test loans, with the same AUC of 0.815 before and after the fix.
> - Expected loss fell from £13.37m to £2.85m with Platt scaling, against £2.61m that actually happened.
> - For this quarter's applicants, the calibrated average was 4.1%, inside the 4.5% appetite. The raw model would have declined 31.9% of them; the calibrated one 3.8%.
>
> **The recommendation:** don't tighten lending. Calibrate the model before its PDs feed pricing or provisions, and watch the headroom, because 4.1% against 4.5% is thin."

### Reflection: what I learned and what I'd do differently
> "Three reflections:
> 1. **The model wasn't wrong in the way people assumed.** The committee heard 'the model is broken', but its ranking was fine. Separating 'does it rank?' from 'are the numbers right?' turned a model rebuild into a two-parameter fix.
> 2. **Rebalancing has a cost that's easy to forget.** Boosting the default rate to 25% for training is a reasonable choice, but the probabilities then carry that 25% prior. Anyone who rebalances owns the recalibration.
> 3. **With real data I'd extend it:** check calibration by segment, such as broker against direct; use a proper exposure-at-default rather than loan amount; and set up quarterly recalibration with an alert when predicted and actual default rates drift apart. The synthetic data has one clean source of distortion; real data would have several."

---

## Decision log: the whole case on one page

| # | Decision | Why | Alternative rejected | Trade-off accepted |
|---|---|---|---|---|
| 0 | Frame it as "can the percentages be taken at face value against the 4.5% appetite?" | Turns "is the model wrong?" into a testable yes/no | "Rebuild the model" | Narrower scope |
| 1 | Test calibration with a reliability curve and calibration error | AUC can't see wrong percentages | Trust the 0.815 AUC | One more metric to explain |
| 2 | Time-based splits; calibrate on mature loans only | Incomplete outcomes bias absolute levels | Calibrate on the latest 6 months | Calibration window is more than a year old |
| 3 | Platt scaling | Lowest error, stable, absorbs drift | Prior correction (misses drift); isotonic (overfits small samples) | Slightly cautious: +10% on losses |
| 4 | Report in committee terms: PD vs appetite, declines, £ loss | The decision is made in those units | Report calibration metrics only | Technical detail moved to appendix |

**Numbers to remember:** raw **18.8%** vs calibrated **4.1%** against **4.5%** appetite · over-stated **5.0x** · AUC **0.815** unchanged · calibration error **15.07 → 0.38** · expected loss **£13.37m → £2.85m** vs **£2.61m** realised · declines **31.9% → 3.8%**.

---

## Likely follow-up questions

**"Why not just retrain the model without rebalancing?"**
> "That's a valid option, and for the next build I'd consider it, or use class weights instead. But the model's ranking was already good, at 0.815 AUC. Retraining means re-validating the whole model; calibration is a small, auditable layer that fixed the actual problem. And even an unbalanced model drifts, so you need a recalibration process anyway."

**"The committee says the model's 18.8% must mean something. They still want to tighten."**
> "I'd show them the history: no quarter above 4.3% since 2023. Then the test loans: the model predicted £13.37m of losses and £2.61m happened. If they're still concerned about the economy, I'd suggest a specific trigger, such as tightening if the calibrated average PD goes above 4.5%, so the decision is tied to evidence."

**"How would you productionise this?"**
> "Store the Platt parameters as part of the model version, so scoring is raw model then calibration. Each quarter, refit on the latest six months of loans with a full 12 months of outcome, compare the old and new calibration on held-out loans, and alert when the predicted and actual default rates drift beyond a set tolerance. Model risk teams will want the reliability curve in every monitoring pack."

**"How would you validate this on real data?"**
> "Back-test on several out-of-time windows, not just one, and check the reliability curve by segment and by price band. I'd also compare expected and realised losses each quarter, which is the test finance will care about."

**"What would make you wrong?"**
> "If the economy turned sharply, the calibration window, which is more than a year old, could under-state current risk. That's why I'd pair it with early-warning indicators, such as arrears at three months on book, which arrive long before 12-month defaults."

---

## Saying it well
- **Lead with the answer for non-technical panels:** "The model ranked risk well, but its percentages were five times too high. Corrected, we were inside appetite."
- **For technical panels**, slow down on why the rebalanced sample inflates probabilities and on the Platt vs isotonic trade-off. That's where the depth shows.
- **Show chart 2** if you can: the raw curve far below the diagonal and the calibrated curve on it makes the point in seconds.
- **Never apologise for it being a portfolio project.** Say what you'd do with real data. That's the senior-level answer.
