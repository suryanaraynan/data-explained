"""
Case file #001 - Is A&E demand rising, or is it just Monday?

Lane:    SQL + analytics
Domain:  NHS / health
Concept: Window functions - rolling averages, LAG, and ROWS vs RANGE

Run:     python analysis.py
Needs:   duckdb, pandas, numpy, matplotlib  (see repo requirements.txt)

The data is SYNTHETIC: generated below with a fixed seed, modelled on the
weekly and winter patterns visible in NHS England's published monthly
A&E Attendances and Emergency Admissions statistics. "Northshire" is fictional.
"""
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
rng = np.random.default_rng(42)

# ---------------------------------------------------------------------------
# 1. Build a realistic daily attendance series (2 years, one hospital trust)
# ---------------------------------------------------------------------------
days = pd.date_range("2024-11-18", "2026-11-15", freq="D")  # 728 days = 104 full weeks
t = np.arange(len(days))

weekday_effect = np.array([1.14, 1.03, 1.00, 0.99, 0.98, 0.92, 0.94])  # Mon..Sun
winter = 1 + 0.05 * np.cos(2 * np.pi * (days.dayofyear - 15) / 365.25)  # peak mid-Jan
trend = 1 + 0.03 * t / 365.25                                            # +3% a year
expected = 420 * weekday_effect[days.dayofweek] * winter * trend
attendances = rng.normal(expected, 18).round().astype(int)

df = pd.DataFrame({"day": days.date, "attendances": attendances})

# Real feeds have gaps: drop 4 days to simulate a reporting outage
missing = pd.to_datetime(["2026-03-09", "2026-03-10", "2026-03-11", "2026-03-12"]).date
df = df[~df["day"].isin(missing)].reset_index(drop=True)

con = duckdb.connect()
con.register("ae_daily", df)

# ---------------------------------------------------------------------------
# 2. The Monday effect: how far is each weekday from the weekly average?
# ---------------------------------------------------------------------------
weekday_index = con.sql("""
    SELECT
        dayname(day)                                         AS weekday,
        round(avg(attendances))                              AS avg_attendances,
        round(100 * avg(attendances) / avg(avg(attendances)) OVER () - 100, 1)
                                                             AS pct_vs_week_avg
    FROM ae_daily
    GROUP BY dayname(day), isodow(day)
    ORDER BY isodow(day)
""").df()

# ---------------------------------------------------------------------------
# 3. Rolling 7-day average - the right way and the subtly wrong way
#    ROWS  counts the last 7 *rows*  -> silently spans 11 days across a gap
#    RANGE counts the last 7 *days*  -> honest about missing data
# ---------------------------------------------------------------------------
rolling = con.sql("""
    SELECT
        day,
        attendances,
        avg(attendances) OVER w_rows                         AS avg7_rows,
        avg(attendances) OVER w_range                        AS avg7_range,
        count(*)         OVER w_range                        AS days_in_window,
        lag(attendances, 7) OVER (ORDER BY day)              AS seven_rows_back
    FROM ae_daily
    WINDOW
        w_rows  AS (ORDER BY day ROWS  BETWEEN 6 PRECEDING AND CURRENT ROW),
        w_range AS (ORDER BY day RANGE BETWEEN INTERVAL 6 DAYS PRECEDING AND CURRENT ROW)
    ORDER BY day
""").df()

rolling["day"] = pd.to_datetime(rolling["day"])
around_gap = rolling[rolling["day"].between("2026-03-13", "2026-03-17")].copy()
around_gap["day"] = around_gap["day"].dt.date

# ---------------------------------------------------------------------------
# 4. Is demand actually rising? Compare like with like:
#    this year's rolling average vs the same weekday-aligned week last year
#    (lag 364 days = exactly 52 weeks, so Mondays line up with Mondays)
# ---------------------------------------------------------------------------
yoy = con.sql("""
    WITH r AS (
        SELECT day,
               avg(attendances) OVER (ORDER BY day
                   RANGE BETWEEN INTERVAL 6 DAYS PRECEDING AND CURRENT ROW) AS avg7,
               count(*) OVER (ORDER BY day
                   RANGE BETWEEN INTERVAL 6 DAYS PRECEDING AND CURRENT ROW) AS n
        FROM ae_daily
    )
    SELECT this.day,
           round(this.avg7, 1)                               AS avg7_now,
           round(last.avg7, 1)                               AS avg7_last_year,
           round(100 * (this.avg7 / last.avg7 - 1), 1)       AS pct_change_yoy
    FROM r AS this
    JOIN r AS last ON last.day = this.day - INTERVAL 364 DAYS
    WHERE this.n = 7 AND last.n = 7
    ORDER BY this.day DESC
    LIMIT 1
""").df()

latest_monday = con.sql("""
    SELECT day, attendances FROM ae_daily
    WHERE isodow(day) = 1 ORDER BY day DESC LIMIT 1
""").df()

# ---------------------------------------------------------------------------
# 5. Print the results used in the write-up
# ---------------------------------------------------------------------------
pd.set_option("display.width", 120)
print("\n== Weekday pattern ==")
print(weekday_index.to_string(index=False))
print("\n== Rolling average just after the 4-day data gap (9-12 Mar 2026) ==")
print(around_gap[["day", "attendances", "avg7_rows", "avg7_range", "days_in_window"]]
      .round(1).to_string(index=False))
print("\n== Latest Monday ==")
print(latest_monday.to_string(index=False))
print("\n== Underlying demand vs same week last year ==")
print(yoy.to_string(index=False))

# ---------------------------------------------------------------------------
# 6. Chart: noisy daily counts vs the 7-day signal
# ---------------------------------------------------------------------------
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
DAILY, SIGNAL = "#c3c2bc", "#2a78d6"

plot = rolling.copy()
plot["day"] = pd.to_datetime(plot["day"])
full = plot.set_index("day").reindex(pd.date_range(plot["day"].min(), plot["day"].max()))
full.loc[full["days_in_window"] < 7, "avg7_range"] = np.nan  # don't plot partial windows

fig, ax = plt.subplots(figsize=(10, 4.6), dpi=150)
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)
ax.plot(full.index, full["attendances"], color=DAILY, lw=1, label="Daily attendances (tall spikes are Mondays)")
ax.plot(full.index, full["avg7_range"], color=SIGNAL, lw=2, label="7-day rolling average")

last = full["avg7_range"].dropna()
ax.annotate("7-day average", (last.index[-1], last.iloc[-1]), xytext=(6, 0),
            textcoords="offset points", va="center", color=INK, fontsize=9)

ax.set_title("Northshire A&E: daily attendances vs 7-day rolling average (synthetic)",
             loc="left", color=INK, fontsize=11, pad=12)
ax.set_ylabel("Attendances per day", color=INK_2, fontsize=9)
ax.grid(axis="y", color=GRID, lw=0.8)
ax.tick_params(colors=INK_2, labelsize=8, length=0)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.legend(loc="upper left", frameon=False, fontsize=8, labelcolor=INK_2, ncol=2)
ax.set_xlim(full.index[0], full.index[-1] + pd.Timedelta(days=60))
fig.tight_layout()
fig.savefig(HERE / "chart.png", facecolor=SURFACE)
print("\nSaved chart.png")
