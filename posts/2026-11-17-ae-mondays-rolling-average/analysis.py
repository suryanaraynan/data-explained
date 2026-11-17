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

import sys

import duckdb
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import viz_style as vs  # noqa: E402
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

# Escalation context: the trust's (fictional) plan opens the escalation ward
# when the 7-day average goes above 480 a day
ESCALATION = 480
full_windows = rolling[rolling["days_in_window"] == 7]
peak = full_windows.loc[full_windows["avg7_range"].idxmax()]
print(f"\n== Escalation check (trigger: 7-day average > {ESCALATION}) ==")
print(f"Highest 7-day average in 2 years: {peak['avg7_range']:.1f} on {peak['day'].date()}")
print(f"Days above trigger: {(full_windows['avg7_range'] > ESCALATION).sum()}")

# Weekday x month: how far each weekday sits from that month's daily average
wm = con.sql("""
    WITH m AS (
        SELECT date_trunc('month', day) AS month, isodow(day) AS dow,
               avg(attendances) AS avg_att
        FROM ae_daily GROUP BY 1, 2
    )
    SELECT month, dow,
           100 * avg_att / avg(avg_att) OVER (PARTITION BY month) - 100 AS pct
    FROM m ORDER BY month, dow
""").df()
grid = wm.pivot(index="dow", columns="month", values="pct")
monday_top = int((grid.idxmax(axis=0) == 1).sum())
print(f"\n== Monday is the busiest weekday in {monday_top} of {grid.shape[1]} months ==")

# ---------------------------------------------------------------------------
# 6. Visuals (house style: tools/viz_style.py)
# ---------------------------------------------------------------------------
FOOT = ("Synthetic data modelled on NHS England A&E Attendances and Emergency Admissions "
        "patterns | Northshire NHS Trust is fictional | Data Explained #001")

# ---- chart_1: the last 12 months, signal vs noise vs last year vs the trigger
r = rolling.set_index("day")
cal = r.reindex(pd.date_range(r.index.min(), r.index.max()))
cal.loc[cal["days_in_window"] < 7, "avg7_range"] = np.nan        # hide partial windows
cal["avg7_last_year"] = cal["avg7_range"].shift(364)            # same weekday, 52 weeks ago
win = cal.loc["2025-11-16":"2026-11-15"]
end = win.index[-1]

fig, ax = vs.figure(height=5.6)
vs.shade(ax, pd.Timestamp("2025-12-01"), pd.Timestamp("2026-02-28"), "Winter")
vs.shade(ax, pd.Timestamp("2026-03-09"), pd.Timestamp("2026-03-13"), "Feed outage",
         color="#e6e5e1")
ax.plot(win.index, win["attendances"], color=vs.MUTED, lw=0.8, zorder=2)
ax.plot(win.index, win["avg7_last_year"], color=vs.INK_3, lw=1.2, ls=(0, (4, 3)), zorder=3)
ax.plot(win.index, win["avg7_range"], color=vs.SERIES[0], lw=2.2, zorder=4)
vs.ref_line(ax, ESCALATION, "Escalation\ntrigger: 480", color=vs.STATUS["critical"])

vs.end_label(ax, end, win["avg7_range"].iloc[-1] + 4,
             f"This year: {win['avg7_range'].iloc[-1]:.0f}", color=vs.INK)
vs.end_label(ax, end, win["avg7_last_year"].iloc[-1] - 6,
             f"Last year: {win['avg7_last_year'].iloc[-1]:.0f}", color=vs.INK_2)
mon = pd.Timestamp(latest_monday["day"].iloc[0])
vs.callout(ax, mon, latest_monday["attendances"].iloc[0],
           "Mon 9 Nov: 538\n19% above that week's average", dx=-150, dy=8,
           marker_color=vs.INK_2)
pk = win["avg7_range"].idxmax()
vs.callout(ax, pk, win["avg7_range"].max(),
           f"Winter peak: {win['avg7_range'].max():.0f} a day\nstill below the trigger",
           dx=40, dy=48, marker_color=vs.SERIES[0])
ax.text(win.index[8], 352, "Daily attendances (grey): the tall spikes are Mondays",
        fontsize=8, color=vs.INK_2)

ax.set_xlim(win.index[0], end)
ax.set_ylim(340, 575)
ax.xaxis.set_major_formatter(__import__("matplotlib.dates").dates.DateFormatter("%b %Y"))
vs.headline(fig, "Underlying A&E demand is up 2.6% on last year, not surging",
            "Northshire NHS Trust, A&E attendances per day: 7-day average (blue) vs same "
            "week last year (dashed)\n16 Nov 2025 to 15 Nov 2026")
vs.footer(fig, FOOT)
vs.save(fig, HERE / "chart_1.png")

# ---- chart_2: weekday x month heatmap, % vs that month's daily average
labels = [d.strftime("%b\n%y") if d.month in (1, 11) or i == 0 else d.strftime("%b")
          for i, d in enumerate(pd.to_datetime(grid.columns))]
fig, ax = vs.figure(height=4.4)
vs.style_axes(ax, grid=None)
fig.subplots_adjust(right=0.90)
ax.spines["bottom"].set_visible(False)
im = ax.imshow(grid.values, cmap=vs.DIV_CMAP, norm=TwoSlopeNorm(0, -20, 20), aspect="auto")
for (i, j), v in np.ndenumerate(grid.values):
    ax.text(j, i, f"{v:+.0f}" if round(v) != 0 else "0", ha="center", va="center", fontsize=6.5,
            color="white" if abs(v) > 12 else vs.INK)
ax.set_yticks(range(7), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
ax.set_xticks(range(grid.shape[1]), labels, fontsize=7)
cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
cb.outline.set_visible(False)
cb.ax.tick_params(labelsize=7, length=0, colors=vs.INK_2)
cb.set_label("% vs month's daily average", fontsize=7.5, color=vs.INK_2)
vs.headline(fig, f"Mondays are the busiest day in {monday_top} of {grid.shape[1]} months",
            "Average attendances by weekday, % above (red) or below (blue) that month's "
            "daily average. Nov 2024 to Nov 2026")
vs.footer(fig, FOOT)
vs.save(fig, HERE / "chart_2.png")
print("\nSaved chart_1.png, chart_2.png")
