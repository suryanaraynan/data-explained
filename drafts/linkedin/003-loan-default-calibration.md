# LinkedIn draft: Case file #003

**Status:** draft, not posted
**Image to attach:** `posts/2026-11-21-loan-default-calibration/chart_2.png` (reliability curve), or chart_1 + chart_3 as a 2-image post
**First comment (put the link here, not in the post, because LinkedIn shows posts with links to fewer people):**
Full case file, Python and charts: https://github.com/suryanaraynan/data-explained/tree/main/posts/2026-11-21-loan-default-calibration

---

A credit model said 18.8% of loan applicants would default. Corrected, it said 4.1%.

The model wasn't broken. Its ranking was fine. Its percentages weren't.

I built a portfolio case on UK-style personal lending. The scenario: a new default model tells a credit committee that applicants are far above the board's 4.5% risk limit. Do they tighten lending?

Three things changed the answer:

1. The model ranked risk well (AUC 0.815) but over-stated it 5.0x. On loans with known outcomes it predicted £13.37m of losses. £2.61m happened.

2. The cause: it was trained on a sample where defaults were boosted to 25% to handle class imbalance. The probabilities kept that 25% prior.

3. Platt scaling, fitted on mature loans, cut calibration error from 15.07 to 0.38 points with the same AUC. This quarter's applicants came out at 4.1%, inside appetite. No need to tighten.

The technical lesson I'll remember: AUC can't see this problem at all. It was 0.815 before and after the fix. If a probability feeds a price, a provision or a threshold, check a reliability curve too.

A model can be right about who is riskier and wrong about how risky.

Have you ever had to explain to a stakeholder that a "good" model's numbers couldn't be taken literally?

#DataScience #MachineLearning #CreditRisk #ModelValidation #PortfolioProject
