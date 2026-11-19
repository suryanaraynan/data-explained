# LinkedIn draft: Case file #002

**Status:** draft, not posted
**Image to attach:** `posts/2026-11-19-energy-tariff-star-schema/chart_3.png` (results), or chart_1 + chart_3 as a 2-image post
**First comment (put the link here, not in the post, because LinkedIn shows posts with links to fewer people):**
Full case file, SQL and charts: https://github.com/suryanaraynan/data-explained/tree/main/posts/2026-11-19-energy-tariff-star-schema

---

The dashboard said a time-of-use tariff was making peak electricity use 33.3% worse.

It was actually 19.1% better. Nothing about the customers changed. Only the join did.

I built a portfolio case on half-hourly smart meter data for a fictional energy supplier. The scenario: a commercial director sees the dashboard and asks whether to close a tariff trial before winter.

What changed the answer:

1. Reconciling to the meter feed. The dashboard query held 48.2% more electricity than the meters recorded, with 1,612,800 duplicate rows.

2. Declaring the grain: one row per meter per half-hour. In a star schema built at that grain, tariff homes used 1.78 kWh at peak per day against 2.20 on a flat rate: 19.1% less, in all 6 regions.

3. Tagging each reading with the tariff in force that day, not today's tariff. Grouping by current tariff had put 18.0% of one group's usage under the wrong label.

The technical lesson: a join to a history table without a date condition doesn't error. It runs, it looks plausible, and it repeats every row once per history entry.

If a number contradicts how the thing is designed to work, check the plumbing first.

How do you test that a pipeline's totals are right before anyone sees them?

#DataEngineering #DataModelling #SQL #EnergyData #PortfolioProject
