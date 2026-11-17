# Case file #NNN: <Question a stakeholder would actually ask?>

**Skill lane:** <lane label> · **Domain:** <domain label> · **Concept:** <concept in plain words>

> **TL;DR:** <2–3 sentences: the question, the answer, the number that matters, the decision.>

---

## 1. The problem

<Who is asking (role at the fictional org), what they saw, what decision is riding on it, and what a wrong answer would cost. No jargon.>

![<alt text: what the stakeholder saw that triggered the question>](chart_1.png)

## 2. The data

<Table(s) and columns. What one row means. Any real-world mess deliberately included (gaps, duplicates, late data).>

> The data is **synthetic**: generated in [`analysis.py`](analysis.py) with a fixed seed, modelled on <real pattern / real public source>. To try this on real data, start from <verified public dataset>.

## 3. The approach and the code

<2–4 steps. Each one: what question this step answers, a short code excerpt (the important lines only), one sentence on why it's done this way.>

<Optional explainer visual here (or in section 6), showing how the method works or a gotcha:>

![<alt text>](chart_2.png)

## 4. What we found

<Results visual (required): the chart or table that answers the question:>

![<alt text: the answer, in words>](chart_3.png)

<Results table and/or 3 bullets with numbers copied from the actual run output. End with **Decision it drives:**.>

## 5. Explain it twice

**To <stakeholder role> (no jargon):**
<At most 3 sentences. No technical terms. Lead with the answer.>

**To a technical interviewer:**
<One paragraph: the method choice, the alternative you rejected and why, the main assumption, how you validated it.>

## 6. When to use it, when not to, and gotchas

**Use it when** <...>

**Don't use it when** <... and what to use instead>

**The same idea in two other industries:**
- **<Industry A>:** <2 sentences: the equivalent problem there, and what changes in how you'd apply the technique.>
- **<Industry B>:** <2 sentences, ideally where the technique needs adapting or breaks.>

**Gotchas:**
1. <A concrete mistake, ideally demonstrated in the code with numbers>
2. <...>
3. <...>

## 7. Interview drill

**Q1. <Concept question>**
<Answer in 3–5 sentences.>

**Q2. <Scenario question: "A stakeholder says X, what do you do?">**
<Answer.>

**Q3. <Trade-off or "why not Y?" question>**
<Answer.>

---

*Run it yourself:* `pip install -r requirements.txt && python posts/<folder>/analysis.py`
