"""
Case file #002 - Is our Saver Nights tariff cutting peak electricity use, or making it worse?

Lane:    Data engineering
Domain:  Energy / utilities
Concept: Star schema / dimensional modelling - declaring the grain, resolving
         dimension keys "as at" the reading, and placeholder (inferred) members
         so facts never go missing

Run:     python analysis.py
Needs:   duckdb, pandas, numpy, matplotlib  (see repo requirements.txt)

The data is SYNTHETIC: generated below with a fixed seed. It is modelled on the
shape of UK half-hourly smart meter data, such as UK Power Networks' Low Carbon
London "SmartMeter Energy Consumption Data in London Households" (London
Datastore), which includes a 2013 dynamic time-of-use tariff trial.
"Brightwater Energy" and its "Saver Nights" tariff are fictional.
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import viz_style as vs  # noqa: E402

rng = np.random.default_rng(19)
pd.set_option("display.width", 140)

# ---------------------------------------------------------------------------
# 1. Source systems, as they arrive
#    - CRM: one row per account (region, current tariff)
#    - Tariff history: one row per account per tariff period (valid_from / valid_to)
#    - Meter feed: one row per account per half-hour (kWh)
# ---------------------------------------------------------------------------
START, DAYS = pd.Timestamp("2026-09-21"), 56          # 21 Sep to 15 Nov 2026, 8 full weeks
dates = pd.date_range(START, periods=DAYS, freq="D")
OPEN = pd.Timestamp("9999-12-31")
REGIONS = ["London", "South East", "Midlands", "North West", "Yorkshire", "Scotland"]

groups = (
    ["standard_1row"] * 600      # always on Standard Variable
    + ["standard_2rows"] * 200   # came off a Fixed 12M deal in March -> Standard Variable
    + ["saver_before"] * 250     # switched Standard -> Saver Nights in the summer
    + ["saver_during"] * 150     # switched Standard -> Saver Nights during the 8 weeks
    + ["new_no_crm"] * 40        # new customers: meters live from 2 Nov, CRM record not loaded yet
)
n = len(groups)
acct = pd.DataFrame({
    "account_id": [f"BW{100000 + i}" for i in rng.permutation(n)],
    "group": groups,
    "region": rng.choice(REGIONS, size=n, p=[0.22, 0.20, 0.18, 0.16, 0.13, 0.11]),
})
switch_dates = pd.to_datetime(["2026-10-12", "2026-10-19", "2026-10-26"])
acct["switch_date"] = pd.NaT
mask = acct["group"] == "saver_during"
acct.loc[mask, "switch_date"] = rng.choice(switch_dates, size=mask.sum())
mask = acct["group"] == "saver_before"
acct.loc[mask, "switch_date"] = (pd.Timestamp("2026-06-01")
                                 + pd.to_timedelta(rng.integers(0, 90, mask.sum()), "D"))

hist_rows = []
for a in acct.itertuples():
    if a.group == "standard_1row":
        hist_rows.append((a.account_id, "Standard Variable", pd.Timestamp("2024-01-01"), OPEN))
    elif a.group == "standard_2rows":
        hist_rows += [(a.account_id, "Fixed 12M", pd.Timestamp("2025-04-01"), pd.Timestamp("2026-04-01")),
                      (a.account_id, "Standard Variable", pd.Timestamp("2026-04-01"), OPEN)]
    elif a.group.startswith("saver"):
        hist_rows += [(a.account_id, "Standard Variable", pd.Timestamp("2024-01-01"), a.switch_date),
                      (a.account_id, "Saver Nights", a.switch_date, OPEN)]
tariff_history = pd.DataFrame(hist_rows, columns=["account_id", "tariff_name", "valid_from", "valid_to"])
unit_rate = {"Standard Variable": 24.5, "Fixed 12M": 26.0, "Saver Nights": 24.0}  # pence/kWh, day rate
tariff_history["unit_rate_p"] = tariff_history["tariff_name"].map(unit_rate)
for c in ("valid_from", "valid_to"):
    tariff_history[c] = [pd.Timestamp(v).date() for v in tariff_history[c]]

crm = acct[acct["group"] != "new_no_crm"][["account_id", "region"]].copy()
current = tariff_history[tariff_history["valid_to"] == OPEN.date()][["account_id", "tariff_name"]]
crm = crm.merge(current.rename(columns={"tariff_name": "current_tariff"}), on="account_id")

# --- half-hourly consumption: daily shape x household size x autumn cooling x noise
hh = np.arange(48) / 2                                  # hour of day at period start
shape = (0.10
         + 0.12 * np.exp(-((hh - 7.5) ** 2) / 2.0)      # morning
         + 0.06 * np.exp(-((hh - 12.5) ** 2) / 10.0)    # daytime
         + 0.30 * np.exp(-((hh - 18.0) ** 2) / 3.0)     # evening peak
         + 0.05 * np.exp(-((hh - 21.5) ** 2) / 2.0))
shape *= 8.4 / shape.sum()                              # ~8.4 kWh/day for an average home
is_peak = (hh >= 16) & (hh < 19)
is_night = hh < 7

size = rng.lognormal(0, 0.35, n)                        # household size: heavy right tail
autumn = np.linspace(0.93, 1.13, DAYS) * rng.normal(1, 0.03, DAYS)
weekend = np.where(dates.dayofweek >= 5, 1.06, 1.0)
day_level = autumn * weekend                            # (DAYS,)

# Saver Nights effect, only on days the account is actually on the tariff:
# 20% of peak use moved away, some of it reappearing overnight
on_saver = np.zeros((n, DAYS), dtype=bool)
sw = acct["switch_date"].values
for i, g in enumerate(acct["group"]):
    if g.startswith("saver"):
        on_saver[i] = dates.values >= sw[i]
saver_mult = np.where(is_peak, 0.80, np.where(is_night, 1.15, 1.0))   # (48,)

base = size[:, None, None] * day_level[None, :, None] * shape[None, None, :]     # (n, DAYS, 48)
mult = np.where(on_saver[:, :, None], saver_mult[None, None, :], 1.0)
kwh = base * mult * rng.lognormal(-0.08, 0.40, base.shape)

live = np.ones((n, DAYS), dtype=bool)                   # new customers only send data from 2 Nov
live[(acct["group"] == "new_no_crm").values] = dates >= pd.Timestamp("2026-11-02")
ai, di, pi = np.nonzero(np.broadcast_to(live[:, :, None], kwh.shape))
readings = pd.DataFrame({
    "account_id": acct["account_id"].values[ai],
    "reading_ts": dates.values[di] + pd.to_timedelta(pi * 30, "min").values,
    "kwh": kwh[ai, di, pi].round(3),
})

con = duckdb.connect()
for name, frame in [("readings", readings), ("crm", crm), ("tariff_history", tariff_history)]:
    con.register(name, frame)

src = con.execute("SELECT count(*) AS n_rows, round(sum(kwh) / 1000, 1) AS mwh FROM readings").fetchone()
print("== Sources ==")
print(f"Meter feed: {src[0]:,} rows, {src[1]:,} MWh, {readings['account_id'].nunique():,} meters")
print(f"CRM accounts: {len(crm):,}   Tariff history rows: {len(tariff_history):,}")
print(f"Meters with no CRM record yet: {readings['account_id'].nunique() - len(crm)}")
rows_per_acct = con.execute("""
    SELECT c.current_tariff, count(*) AS accounts, round(avg(n), 2) AS history_rows_per_account
    FROM crm c JOIN (SELECT account_id, count(*) AS n FROM tariff_history GROUP BY 1) h USING (account_id)
    GROUP BY 1 ORDER BY 1 DESC
""").df()
print(rows_per_acct.to_string(index=False))

# ---------------------------------------------------------------------------
# 2. The flat dashboard query (what the commercial director saw)
#    Joins the meter feed to tariff history on account only, to pick up a unit rate,
#    then groups by the CRM's *current* tariff.
# ---------------------------------------------------------------------------
flat_sql = """
    SELECT c.current_tariff,
           sum(r.kwh) FILTER (WHERE hour(r.reading_ts) >= 16 AND hour(r.reading_ts) < 19)
             / count(DISTINCT (r.account_id, CAST(r.reading_ts AS DATE))) AS peak_kwh_per_home_day,
           sum(r.kwh * h.unit_rate_p) / 100                                AS cost_gbp
    FROM readings r
    JOIN tariff_history h ON h.account_id = r.account_id        -- no date condition: fans out
    JOIN crm c            ON c.account_id = r.account_id
    GROUP BY c.current_tariff ORDER BY 1 DESC
"""
flat = con.execute(flat_sql).df()
flat_std = flat.loc[flat["current_tariff"] == "Standard Variable", "peak_kwh_per_home_day"].iloc[0]
flat_sav = flat.loc[flat["current_tariff"] == "Saver Nights", "peak_kwh_per_home_day"].iloc[0]
flat_diff = 100 * (flat_sav / flat_std - 1)
print("\n== Flat dashboard: peak (16:00-19:00) kWh per household per day ==")
print(flat[["current_tariff", "peak_kwh_per_home_day"]].round(2).to_string(index=False))
print(f"Saver Nights vs Standard (dashboard): {flat_diff:+.1f}%")

flat_rows = con.execute("""
    SELECT count(*) AS n_rows, round(sum(r.kwh) / 1000, 1) AS mwh,
           count(*) - count(DISTINCT (r.account_id, r.reading_ts)) AS duplicate_rows
    FROM readings r
    JOIN tariff_history h ON h.account_id = r.account_id
    JOIN crm c            ON c.account_id = r.account_id
""").fetchone()
print(f"Flat join: {flat_rows[0]:,} rows, {flat_rows[1]:,} MWh, "
      f"{flat_rows[2]:,} duplicate meter-half-hours")

# ---------------------------------------------------------------------------
# 3. The star schema
#    Grain of the fact: ONE row per meter per half-hour settlement period.
#    Dimensions: date, time-of-day (half-hour period), customer, tariff.
# ---------------------------------------------------------------------------
con.execute("""
CREATE TABLE dim_date AS
SELECT CAST(strftime(d, '%Y%m%d') AS INT) AS date_key, CAST(d AS DATE) AS date,
       dayname(d) AS weekday, isodow(d) >= 6 AS is_weekend
FROM range(DATE '2026-09-21', DATE '2026-11-16', INTERVAL 1 DAY) t(d);

CREATE TABLE dim_time AS
SELECT p AS period_key,
       strftime(TIMESTAMP '2000-01-01' + (p - 1) * INTERVAL 30 MINUTE, '%H:%M') AS start_time,
       p BETWEEN 33 AND 38 AS is_peak,                       -- 16:00 to 18:59
       CASE WHEN p BETWEEN 33 AND 38 THEN 'Peak 16:00-19:00'
            WHEN p <= 14 THEN 'Night 00:00-07:00' ELSE 'Day' END AS band
FROM range(1, 49) t(p);

CREATE TABLE dim_tariff AS
SELECT * FROM (VALUES
    (-1, 'Unknown', 'Unknown', NULL),
    ( 1, 'Standard Variable', 'Flat rate', FALSE),
    ( 2, 'Fixed 12M',         'Flat rate', FALSE),
    ( 3, 'Saver Nights',      'Time of use', TRUE)
) t(tariff_key, tariff_name, tariff_group, is_time_of_use);

-- customer dimension: surrogate key per account, from CRM
CREATE TABLE dim_customer AS
SELECT row_number() OVER (ORDER BY account_id) AS customer_key,
       account_id, region, FALSE AS is_placeholder
FROM crm;
""")

# The tempting version: inner join the feed to the customer dimension
inner = con.execute("""
    SELECT count(*) AS n_rows, round(sum(r.kwh) / 1000, 1) AS mwh
    FROM readings r JOIN dim_customer c USING (account_id)
""").fetchone()

# The right version: add a placeholder row for every meter the CRM hasn't caught up with,
# so its readings still land in the fact table (and get repaired when the CRM record arrives)
con.execute("""
INSERT INTO dim_customer
SELECT (SELECT max(customer_key) FROM dim_customer) + row_number() OVER (ORDER BY account_id),
       account_id, 'Unknown (not in CRM yet)', TRUE
FROM (SELECT DISTINCT account_id FROM readings
      WHERE account_id NOT IN (SELECT account_id FROM crm));

-- fact load: every key is resolved AS AT the reading, not as of today
CREATE TABLE fact_usage AS
SELECT CAST(strftime(r.reading_ts, '%Y%m%d') AS INT)                AS date_key,
       hour(r.reading_ts) * 2 + minute(r.reading_ts) // 30 + 1      AS period_key,
       c.customer_key,
       coalesce(t.tariff_key, -1)                                    AS tariff_key,
       r.kwh
FROM readings r
JOIN dim_customer c ON c.account_id = r.account_id                   -- every meter has a row now
LEFT JOIN tariff_history h
       ON h.account_id = r.account_id
      AND CAST(r.reading_ts AS DATE) >= h.valid_from
      AND CAST(r.reading_ts AS DATE) <  h.valid_to                   -- the tariff in force that day
LEFT JOIN dim_tariff t ON t.tariff_name = h.tariff_name;
""")

star = con.execute("""
    SELECT count(*) AS n_rows, round(sum(kwh) / 1000, 1) AS mwh,
           count(*) - count(DISTINCT (customer_key, date_key, period_key)) AS duplicate_rows,
           count(*) FILTER (WHERE tariff_key = -1) AS unknown_tariff_rows
    FROM fact_usage
""").fetchone()
placeholders = con.execute("SELECT count(*) FROM dim_customer WHERE is_placeholder").fetchone()[0]

recon = pd.DataFrame({
    "Stage": ["Meter feed (source)",
              "Flat dashboard query",
              "Star, inner joins only",
              "Star + placeholder rows"],
    "Rows": [src[0], flat_rows[0], inner[0], star[0]],
    "MWh": [src[1], flat_rows[1], inner[1], star[1]],
    "vs feed": [0.0, 100 * (flat_rows[1] / src[1] - 1), 100 * (inner[1] / src[1] - 1),
                100 * (star[1] / src[1] - 1)],
    "Grain check": ["1 row per meter per half-hour",
                    f"Fails: {flat_rows[2]:,} duplicates", f"Passes, {placeholders} meters lost",
                    "Passes"],
})
print("\n== Reconciliation to the meter feed ==")
print(recon.round(1).to_string(index=False))
print(f"Placeholder customer rows: {placeholders}; fact rows with unknown tariff: {star[3]:,}")
print(f"kWh dropped by the inner join: {src[1] - inner[1]:.1f} MWh "
      f"({100 * (1 - inner[1] / src[1]):.1f}% of the feed)")

# ---------------------------------------------------------------------------
# 4. The answer, from the star schema
# ---------------------------------------------------------------------------
con.execute("""
CREATE VIEW home_day AS
SELECT f.customer_key, f.date_key, t.tariff_group, c.region,
       sum(f.kwh) FILTER (WHERE tm.is_peak) AS peak_kwh,
       sum(f.kwh)                           AS total_kwh
FROM fact_usage f
JOIN dim_time tm    USING (period_key)
JOIN dim_tariff t   USING (tariff_key)
JOIN dim_customer c USING (customer_key)
WHERE f.tariff_key <> -1
GROUP BY ALL
""")
res = con.execute("""
    SELECT tariff_group,
           count(*)                          AS household_days,
           round(avg(peak_kwh), 2)           AS peak_kwh_per_home_day,
           round(avg(total_kwh), 2)          AS total_kwh_per_home_day,
           round(100 * sum(peak_kwh) / sum(total_kwh), 1) AS peak_share_pct
    FROM home_day GROUP BY 1 ORDER BY 1
""").df()
std = res.set_index("tariff_group").loc["Flat rate"]
sav = res.set_index("tariff_group").loc["Time of use"]
star_diff = 100 * (sav["peak_kwh_per_home_day"] / std["peak_kwh_per_home_day"] - 1)
total_diff = 100 * (sav["total_kwh_per_home_day"] / std["total_kwh_per_home_day"] - 1)
print("\n== Star schema: tariff in force on the day ==")
print(res.to_string(index=False))
print(f"Saver Nights vs flat-rate, peak kWh per household-day: {star_diff:+.1f}%")
print(f"Saver Nights vs flat-rate, total kWh per household-day: {total_diff:+.1f}%")

by_region = con.execute("""
    SELECT region,
           round(100 * (avg(peak_kwh) FILTER (WHERE tariff_group = 'Time of use')
                      / avg(peak_kwh) FILTER (WHERE tariff_group = 'Flat rate') - 1), 1)
             AS saver_vs_flat_pct
    FROM home_day GROUP BY 1 ORDER BY 2
""").df()
print("\n== Peak use, Saver Nights vs flat-rate, by region ==")
print(by_region.to_string(index=False))
print(f"Regions where Saver Nights is lower at peak: "
      f"{(by_region['saver_vs_flat_pct'] < 0).sum()} of {len(by_region)}")

# Within-household check: the 150 mid-period switchers, before vs after, each day
# indexed to that same day's flat-rate average (so colder weeks don't muddy it)
sw_ids = acct.loc[acct["group"] == "saver_during", "account_id"]
con.register("switchers", pd.DataFrame({"account_id": sw_ids}))
switch = con.execute("""
    WITH flat_day AS (
        SELECT date_key, avg(peak_kwh) AS flat_avg FROM home_day
        WHERE tariff_group = 'Flat rate' GROUP BY 1)
    SELECT CASE WHEN h.tariff_group = 'Time of use' THEN 'after' ELSE 'before' END AS period,
           count(DISTINCT h.customer_key)                       AS households,
           round(100 * (avg(h.peak_kwh / fd.flat_avg) - 1), 1) AS pct_vs_flat_rate_same_day
    FROM home_day h
    JOIN dim_customer c USING (customer_key)
    JOIN switchers s    USING (account_id)
    JOIN flat_day fd    USING (date_key)
    GROUP BY 1 ORDER BY 1 DESC
""").df()
print("\n== Mid-period switchers: peak use vs the flat-rate average on the same day ==")
print(switch.to_string(index=False))

# Gotcha: labelling by *current* tariff puts switchers' pre-switch usage under Saver Nights
mislabel = con.execute("""
    SELECT round(100 * sum(f.kwh) FILTER (WHERE f.tariff_key <> 3) / sum(f.kwh), 1)
    FROM fact_usage f JOIN dim_customer c USING (customer_key)
    JOIN crm USING (account_id) WHERE crm.current_tariff = 'Saver Nights'
""").fetchone()[0]
print(f"\nShare of 'current tariff = Saver Nights' kWh actually used on Standard Variable: "
      f"{mislabel}%")

# Gotcha: a hard-coded 'hour BETWEEN 16 AND 19' is 4 hours, not 3
btw = con.execute("""
    SELECT round(avg(p), 2) FROM (
        SELECT sum(kwh) FILTER (WHERE hour(reading_ts) BETWEEN 16 AND 19) AS p
        FROM readings GROUP BY account_id, CAST(reading_ts AS DATE))
""").fetchone()[0]
flag = con.execute("SELECT round(avg(p), 2) FROM (SELECT sum(kwh) FILTER (WHERE is_peak) AS p "
               "FROM fact_usage JOIN dim_time USING (period_key) "
               "GROUP BY customer_key, date_key)").fetchone()[0]
print(f"Peak kWh per household-day, 'hour BETWEEN 16 AND 19': {btw:.2f}  vs  dim_time.is_peak: {flag:.2f} "
      f"({100 * (btw / flag - 1):+.1f}%)")

TARGET = -10.0
print(f"\n== Trial business case: Saver Nights peak use at least {abs(TARGET):.0f}% below flat-rate ==")
print(f"Dashboard says {flat_diff:+.1f}% -> {'met' if flat_diff <= TARGET else 'NOT met'}")
print(f"Star schema says {star_diff:+.1f}% -> {'met' if star_diff <= TARGET else 'NOT met'}")

# ---------------------------------------------------------------------------
# 5. Visuals (house style: tools/viz_style.py)
# ---------------------------------------------------------------------------
FOOT = ("Synthetic data modelled on UK Power Networks' Low Carbon London smart meter data "
        "| Brightwater Energy is fictional | Data Explained #002")

# ---- chart_1 (context): the dashboard tile the commercial director saw
fig, ax = vs.figure(height=4.2)
fig.subplots_adjust(top=0.74, bottom=0.18, left=0.20, right=0.80)
ax.grid(False)
vs.style_axes(ax, grid="x")
labels = ["Standard Variable", "Saver Nights"]
vals = [flat_std, flat_sav]
ax.barh(labels, vals, height=0.55, color=[vs.MUTED, vs.SERIES[0]], zorder=3)
for y, v in enumerate(vals):
    ax.text(v + 0.03, y, f"{v:.2f} kWh", va="center", fontsize=9.5, color=vs.INK,
            fontweight="bold" if y == 1 else "normal")
tgt = flat_std * (1 + TARGET / 100)
ax.axvline(tgt, color=vs.STATUS["critical"], lw=1.2, ls="--", zorder=4)
ax.text(tgt - 0.06, 1.45, f"Trial target: at least 10% below\nStandard ({tgt:.2f} kWh)",
        fontsize=8, color=vs.INK_2, ha="right", va="bottom")
ax.text(flat_sav + 0.80, 1, f"{flat_diff:+.1f}% vs Standard:\nthe wrong side of the target",
        fontsize=8.5, color=vs.STATUS["critical"], va="center")
ax.set_xlim(0, max(vals) * 1.75)
ax.set_ylim(-0.5, 1.9)
ax.tick_params(axis="y", labelsize=9.5)
ax.set_xlabel("kWh per household per day, 16:00-19:00", fontsize=8.5)
vs.headline(fig, f"The dashboard said Saver Nights homes use {flat_diff:.1f}% more at peak",
            "Brightwater Energy tariff dashboard (flat query), peak-time electricity per "
            "household per day by current tariff\n21 Sep to 15 Nov 2026")
vs.footer(fig, FOOT)
vs.save(fig, HERE / "chart_1.png")

# ---- chart_2 (explainer): reconciliation table, every stage vs the meter feed
vs.table_png(
    recon, HERE / "chart_2.png",
    title="Only the star schema with placeholder rows matches the meter feed",
    subtitle=("Rows and total electricity at each stage, compared with the raw half-hourly "
              "meter feed\n21 Sep to 15 Nov 2026"),
    footer_text=FOOT, highlight_rows=(3,),
    col_formats={"Rows": "{:,}", "MWh": "{:,.1f}", "vs feed": "{:+.1f}%"},
    col_width=2.2, row_height=0.36,
)

# ---- chart_3 (results): average day, Saver Nights vs flat-rate, from the star schema
prof = con.execute("""
    SELECT tm.period_key, tm.start_time, t.tariff_group,
           sum(f.kwh) / count(DISTINCT (f.customer_key, f.date_key)) AS kwh
    FROM fact_usage f JOIN dim_time tm USING (period_key) JOIN dim_tariff t USING (tariff_key)
    WHERE f.tariff_key <> -1 GROUP BY ALL ORDER BY 1
""").df().pivot(index="period_key", columns="tariff_group", values="kwh")
x = (prof.index.values - 1) / 2
night_diff = con.execute("""
    SELECT round(100 * (sum(kwh) FILTER (WHERE g = 'Time of use') / sum(n) FILTER (WHERE g = 'Time of use'))
               / (sum(kwh) FILTER (WHERE g = 'Flat rate') / sum(n) FILTER (WHERE g = 'Flat rate')) - 100, 1)
    FROM (SELECT t.tariff_group AS g, sum(f.kwh) AS kwh,
                 count(DISTINCT (f.customer_key, f.date_key)) AS n
          FROM fact_usage f JOIN dim_time tm USING (period_key) JOIN dim_tariff t USING (tariff_key)
          WHERE tm.band = 'Night 00:00-07:00' AND f.tariff_key <> -1 GROUP BY 1)
""").fetchone()[0]
print(f"Night (00:00-07:00) kWh per household-day, Saver Nights vs flat-rate: {night_diff:+.1f}%")

fig, ax = vs.figure(height=5.4)
vs.shade(ax, 16, 19, "Peak 16:00-19:00")
vs.shade(ax, 0, 7, "Saver Nights cheap rate 00:00-07:00", color="#f6f5f2")
ax.step(np.append(x, 24), np.append(prof["Flat rate"].values, prof["Flat rate"].values[-1]),
        where="post", color=vs.MUTED, lw=2.0, zorder=3)
ax.step(np.append(x, 24), np.append(prof["Time of use"].values, prof["Time of use"].values[-1]),
        where="post", color=vs.SERIES[0], lw=2.2, zorder=4)
vs.end_label(ax, 24, prof["Flat rate"].values[-1] + 0.012, "Flat-rate homes", color=vs.INK_2)
vs.end_label(ax, 24, prof["Time of use"].values[-1] - 0.012, "Saver Nights homes", color=vs.SERIES[0])
pk = 18.0
vs.callout(ax, pk, prof.loc[37, "Time of use"],
           f"Peak: {sav['peak_kwh_per_home_day']:.2f} vs {std['peak_kwh_per_home_day']:.2f} kWh\n"
           f"per household-day ({star_diff:+.1f}%)", dx=-80, dy=30, marker_color=vs.SERIES[0],
           ha="right")
vs.callout(ax, 3.0, prof.loc[7, "Time of use"],
           f"Overnight: {night_diff:+.1f}%\n(some use moved, not lost)", dx=-20, dy=95,
           marker_color=vs.SERIES[0])
ax.set_xlim(0, 24)
ax.set_ylim(0, prof.values.max() * 1.25)
ax.set_xticks(range(0, 25, 3), [f"{h:02d}:00" for h in range(0, 25, 3)])
ax.set_ylabel("kWh per half-hour, average household", fontsize=8.5)
vs.headline(fig, f"Saver Nights homes use {abs(star_diff):.1f}% less at peak, not "
                 f"{flat_diff:.1f}% more",
            "Brightwater Energy, average electricity per household per half-hour, by the tariff "
            "in force that day (star schema)\n21 Sep to 15 Nov 2026")
vs.footer(fig, FOOT)
vs.save(fig, HERE / "chart_3.png")
print("\nSaved chart_1.png, chart_2.png, chart_3.png")
