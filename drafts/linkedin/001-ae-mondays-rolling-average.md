# LinkedIn draft: Case file #001

**Status:** draft, not posted
**Image to attach:** `posts/2026-11-17-ae-mondays-rolling-average/chart_3.png` (results), or chart_1 + chart_3 as a 2-image post
**First comment (put the link here, not in the post, because LinkedIn shows posts with links to fewer people):**
Full case file, SQL and charts: https://github.com/suryanaraynan/data-explained/tree/main/posts/2026-11-17-ae-mondays-rolling-average

---

538 A&E attendances on a Monday. Is the hospital surging?

Probably not. And the reason is one of the most useful habits in data work.

I built a portfolio case on NHS-style A&E data. The scenario: an operations director sees a big Monday number and asks whether to open the escalation ward.

Three things changed the answer:

1. Mondays are always busy. They ran 14% above an average day in every one of 25 months, so a big Monday is the normal pattern, not news.

2. A 7-day rolling average removes the weekly cycle. It showed underlying demand up 2.6% on last year: real growth, but gradual.

3. The trust's trigger was a 7-day average above 480. It never crossed it. Even the winter peak was 470.

So the answer was: don't open the ward for one Monday. Plan for winter instead.

The technical lesson I'll remember: with gaps in the data, a "last 7 rows" window silently covered 11 days. A "last 7 days" window flagged the problem. Same SQL, one word different.

Before you react to a number, ask: compared with what?

What's the most misleading single number you've seen on a dashboard?

#DataAnalytics #SQL #NHS #DataStorytelling #PortfolioProject
