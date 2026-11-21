"""
Case file #003 - The new model says 18.8% of applicants will default. Do we tighten lending, or is the model wrong?

Lane:    Stats + ML
Domain:  Banking / finance
Concept: Probability calibration (reliability curves, Platt scaling, isotonic
         regression, and correcting for a rebalanced training sample)

Run:     python analysis.py
Needs:   pandas, numpy, scikit-learn, matplotlib  (see repo requirements.txt)

The data is SYNTHETIC: generated below with a fixed seed. It is modelled on the
shape of UK unsecured personal lending (a low single-digit default rate, risk
driven by bureau score, missed payments and debt-to-income) and on public
credit-default datasets such as UCI's "Default of Credit Card Clients".
"Thamesgate Building Society" is fictional, and so are its risk appetite,
pricing bands and loss assumptions.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import viz_style as vs  # noqa: E402

rng = np.random.default_rng(2026)
pd.set_option("display.width", 140)

SNAPSHOT = pd.Timestamp("2026-10-31")   # outcomes observed up to this date
LGD = 0.75                              # fictional loss given default, unsecured
RISK_APPETITE = 0.045                   # fictional board limit on average PD of new lending
FEATURES = ["bureau_score", "missed_payments_2y", "dti", "income_k",
            "loan_amount", "term_months", "months_employed", "channel_code"]


# ---------------------------------------------------------------------------
# 1. Build realistic loan-level data
#    One row per personal loan: applicant features at application, and whether
#    the loan defaulted (90+ days past due) within 12 months of being drawn.
# ---------------------------------------------------------------------------
def make_loans(n, months, base_logit_by_month):
    month = rng.choice(months, size=n)
    channel = rng.choice(["direct", "broker", "branch"], size=n, p=[0.5, 0.35, 0.15])
    score = np.clip(rng.normal(780, 90, n), 400, 999).round()
    missed = rng.poisson(np.where(score < 700, 0.9, 0.25))
    income = np.round(np.exp(rng.normal(np.log(34), 0.45, n)), 1)            # £k a year
    loan = np.clip(np.round(np.exp(rng.normal(np.log(8000), 0.6, n)), -2), 1000, 25000)
    dti = np.clip(rng.gamma(4, 7, n) + 2000 * loan / (income * 1000) * 0.4, 1, 95).round(1)
    term = rng.choice([12, 24, 36, 48, 60], size=n, p=[0.08, 0.2, 0.32, 0.2, 0.2])
    employed = np.clip(rng.exponential(60, n), 0, 480).round()
    chan_code = pd.Series(channel).map({"direct": 0, "broker": 1, "branch": 2}).to_numpy()

    z = (score - 780) / 90
    logit = (base_logit_by_month[pd.DatetimeIndex(month).strftime("%Y-%m")].to_numpy()
             - 1.05 * z + 0.25 * np.maximum(-z - 1, 0) ** 2   # risk climbs faster at the bottom
             + 0.45 * np.minimum(missed, 4)
             + 0.035 * np.maximum(dti - 35, 0)                 # debt burden bites above 35%
             + 0.25 * (chan_code == 1)                         # broker loans run riskier
             - 0.004 * np.minimum(employed, 120)
             + 0.05 * (term - 36) / 12)
    p_true = 1 / (1 + np.exp(-logit))
    defaults = rng.random(n) < p_true
    # month (1-12) in which a default happens; most land in months 4-9
    default_mob = np.clip(np.round(rng.normal(7, 2.5, n)), 1, 12)

    df = pd.DataFrame({
        "loan_id": np.arange(n), "orig_month": pd.DatetimeIndex(month),
        "channel": channel, "channel_code": chan_code, "bureau_score": score,
        "missed_payments_2y": missed, "dti": dti, "income_k": income,
        "loan_amount": loan, "term_months": term, "months_employed": employed,
        "_will_default": defaults, "_default_mob": default_mob,
    })
    # Real-world mess #1: outcomes arrive late. We only *see* a default once it
    # has happened, so loans with < 12 months on book have incomplete outcomes.
    mob = ((SNAPSHOT.year - df.orig_month.dt.year) * 12
           + (SNAPSHOT.month - df.orig_month.dt.month))
    df["months_on_book"] = mob
    df["mature"] = mob >= 12
    df["default_12m"] = (df["_will_default"] & (df["_default_mob"] <= mob)).astype(int)
    return df.drop(columns=["_will_default", "_default_mob"])


months = pd.date_range("2023-01-01", "2026-03-01", freq="MS")
# Underlying risk drifts up slightly over time (cost-of-living pressure)
drift = pd.Series(-6.40 + 0.010 * np.arange(len(months)) + 0.04 * np.sin(np.arange(len(months)) / 3),
                  index=months.strftime("%Y-%m"))
loans = make_loans(95_000, months, drift)

# This quarter's applications (Jul-Sep 2026): no outcomes yet, scored by the model
app_months = pd.date_range("2026-07-01", "2026-09-01", freq="MS")
app_drift = pd.Series(drift.iloc[-1], index=app_months.strftime("%Y-%m"))
applicants = make_loans(7_500, app_months, app_drift)

print("== Loan book ==")
print(f"Loans originated Jan 2023 - Mar 2026: {len(loans):,}")
print(f"Applications this quarter (Jul-Sep 2026): {len(applicants):,}")

q = loans.assign(quarter=loans.orig_month.dt.to_period("Q").astype(str))
cohorts = q.groupby("quarter").agg(loans=("loan_id", "size"), mature_share=("mature", "mean"),
                                   default_rate=("default_12m", "mean")).reset_index()
print("\n== 12-month default rate by origination quarter (as observed on 31 Oct 2026) ==")
print(cohorts.assign(default_rate=lambda d: (100 * d.default_rate).round(2),
                     mature_share=lambda d: (100 * d.mature_share).round(0)).to_string(index=False))
mature_cohorts = cohorts[cohorts.mature_share == 1]
print(f"Highest fully-observed quarter: {100 * mature_cohorts.default_rate.max():.1f}% "
      f"({mature_cohorts.loc[mature_cohorts.default_rate.idxmax(), 'quarter']})")

# ---------------------------------------------------------------------------
# 2. Time-based splits (never random splits for credit models)
#    train:        loans originated 2023-2024
#    calibration:  Jan-Jun 2025 (mature only)
#    test:         Jul-Oct 2025 (mature only: the latest loans with 12 months of outcome)
# ---------------------------------------------------------------------------
train_full = loans[loans.orig_month <= "2024-12-01"]
calib = loans[(loans.orig_month >= "2025-01-01") & (loans.orig_month <= "2025-06-01")]
test = loans[(loans.orig_month >= "2025-07-01") & loans.mature]
assert calib.mature.all()

# Real-world mess #2: the previous model build "fixed" class imbalance by keeping
# every default but only some of the good loans, so defaults are 25% of training rows.
bad = train_full[train_full.default_12m == 1]
good = train_full[train_full.default_12m == 0]
n_good_keep = 3 * len(bad)
beta = n_good_keep / len(good)                    # share of good loans kept
train = pd.concat([bad, good.sample(n_good_keep, random_state=7)])
print("\n== Splits ==")
print(f"Train (2023-2024): {len(train_full):,} loans, default rate {100 * train_full.default_12m.mean():.2f}%")
print(f"  rebalanced training sample: {len(train):,} rows, default rate "
      f"{100 * train.default_12m.mean():.2f}% (kept {100 * beta:.1f}% of good loans)")
print(f"Calibration (Jan-Jun 2025): {len(calib):,} loans, {calib.default_12m.sum()} defaults, "
      f"default rate {100 * calib.default_12m.mean():.2f}%")
print(f"Test (Jul-Oct 2025): {len(test):,} loans, {test.default_12m.sum()} defaults, "
      f"default rate {100 * test.default_12m.mean():.2f}%")

model = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, max_leaf_nodes=15,
                                       random_state=0)
model.fit(train[FEATURES], train.default_12m)


def raw_pd(df):
    return model.predict_proba(df[FEATURES])[:, 1]


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


# ---------------------------------------------------------------------------
# 3. Calibration fixes
# ---------------------------------------------------------------------------
def prior_correct(p):
    """Undo the effect of keeping only a fraction beta of good loans:
    true odds = beta x training odds."""
    return beta * p / (beta * p + 1 - p)


p_cal_raw = raw_pd(calib)
platt = LogisticRegression(C=1e6).fit(logit(p_cal_raw).reshape(-1, 1), calib.default_12m)
iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(p_cal_raw, calib.default_12m)


def platt_pd(p):
    return platt.predict_proba(logit(p).reshape(-1, 1))[:, 1]


def iso_pd(p):
    return iso.predict(p)


def ece(y, p, bins=10):
    """Expected calibration error: average gap between predicted and observed
    default rate across 10 equal-sized groups of loans, weighted by group size."""
    g = pd.qcut(p, bins, labels=False, duplicates="drop")
    t = pd.DataFrame({"y": y, "p": p, "g": g}).groupby("g").agg(y=("y", "mean"), p=("p", "mean"),
                                                              n=("y", "size"))
    return float((t.n * (t.p - t.y).abs()).sum() / t.n.sum())


def reliability(y, p, bins=10):
    g = pd.qcut(p, bins, labels=False, duplicates="drop")
    return (pd.DataFrame({"y": y, "p": p, "g": g}).groupby("g")
            .agg(predicted=("p", "mean"), observed=("y", "mean"), loans=("y", "size")).reset_index())


y_test = test.default_12m.to_numpy()
p_test_raw = raw_pd(test)
methods = {
    "Raw model": p_test_raw,
    "Prior correction": prior_correct(p_test_raw),
    "Platt scaling": platt_pd(p_test_raw),
    "Isotonic regression": iso_pd(p_test_raw),
}
realised_loss = float((y_test * LGD * test.loan_amount).sum())
rows = []
for name, p in methods.items():
    rows.append({
        "method": name,
        "AUC": roc_auc_score(y_test, p),
        "Brier": brier_score_loss(y_test, p),
        "ECE_pct": 100 * ece(y_test, p),
        "avg_PD_pct": 100 * p.mean(),
        "expected_loss_gbp_m": float((p * LGD * test.loan_amount).sum()) / 1e6,
    })
results = pd.DataFrame(rows)
print("\n== Test set (Jul-Oct 2025 loans, outcomes known) ==")
print(results.round({"AUC": 3, "Brier": 4, "ECE_pct": 2, "avg_PD_pct": 2,
                     "expected_loss_gbp_m": 2}).to_string(index=False))
print(f"Actual default rate: {100 * y_test.mean():.2f}%  |  realised loss: £{realised_loss / 1e6:.2f}m")
for _, r in results.iterrows():
    print(f"  {r.method:<20} expected loss vs realised: "
          f"{100 * (r.expected_loss_gbp_m * 1e6 / realised_loss - 1):+.0f}%")

rel_raw = reliability(y_test, p_test_raw)
rel_platt = reliability(y_test, methods["Platt scaling"])
print("\n== Reliability table, raw model (test set, 10 equal-sized groups) ==")
print(rel_raw.assign(predicted=lambda d: (100 * d.predicted).round(1),
                     observed=lambda d: (100 * d.observed).round(1)).to_string(index=False))
print("\n== Reliability table, after Platt scaling ==")
print(rel_platt.assign(predicted=lambda d: (100 * d.predicted).round(1),
                       observed=lambda d: (100 * d.observed).round(1)).to_string(index=False))
print(f"\nRaw model over-states risk by {p_test_raw.mean() / y_test.mean():.1f}x on average")

# ---------------------------------------------------------------------------
# 4. What it means for this quarter's applicants
# ---------------------------------------------------------------------------
BANDS = [0, 0.02, 0.05, 0.10, 0.20, 1.0]
BAND_NAMES = ["A (<2%)", "B (2-5%)", "C (5-10%)", "D (10-20%)", "Decline (20%+)"]
p_app_raw = raw_pd(applicants)
p_app_platt = platt_pd(p_app_raw)
band_mix = pd.DataFrame({
    "band": BAND_NAMES,
    "raw_pct": 100 * pd.Series(pd.cut(p_app_raw, BANDS, labels=BAND_NAMES, right=False))
    .value_counts(normalize=True).reindex(BAND_NAMES).to_numpy(),
    "platt_pct": 100 * pd.Series(pd.cut(p_app_platt, BANDS, labels=BAND_NAMES, right=False))
    .value_counts(normalize=True).reindex(BAND_NAMES).to_numpy(),
})
print("\n== This quarter's applicants (Jul-Sep 2026) ==")
print(f"Average PD, raw model:     {100 * p_app_raw.mean():.1f}%")
print(f"Average PD, Platt scaling: {100 * p_app_platt.mean():.1f}%")
print(f"Board risk appetite:       {100 * RISK_APPETITE:.1f}%")
print("\nPricing band mix (% of applicants)")
print(band_mix.round(1).to_string(index=False))

# ---------------------------------------------------------------------------
# 5. Gotchas, shown in code
# ---------------------------------------------------------------------------
print("\n== Gotcha 1: calibrating on the most recent loans, before their outcomes are in ==")
recent = loans[loans.orig_month >= "2025-10-01"]          # the latest 6 months of lending
print(f"Most recent 6 months (Oct 2025 - Mar 2026): {len(recent):,} loans, "
      f"{100 * (~recent.mature).mean():.0f}% with < 12 months on book, "
      f"observed default rate so far {100 * recent.default_12m.mean():.2f}%")
platt_naive = LogisticRegression(C=1e6).fit(logit(raw_pd(recent)).reshape(-1, 1),
                                            recent.default_12m)
p_naive = platt_naive.predict_proba(logit(p_test_raw).reshape(-1, 1))[:, 1]
el_naive = float((p_naive * LGD * test.loan_amount).sum())
print(f"Test avg PD after calibrating on them: {100 * p_naive.mean():.2f}% "
      f"vs actual {100 * y_test.mean():.2f}%  (ECE {100 * ece(y_test, p_naive):.2f} pts, "
      f"expected loss £{el_naive / 1e6:.2f}m vs realised £{realised_loss / 1e6:.2f}m)")

print("\n== Gotcha 2: isotonic regression on a small calibration set ==")
small = calib.sample(1500, random_state=3)
p_small = raw_pd(small)
iso_small = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(p_small, small.default_12m)
platt_small = LogisticRegression(C=1e6).fit(logit(p_small).reshape(-1, 1), small.default_12m)
p_iso_s = iso_small.predict(p_test_raw)
p_platt_s = platt_small.predict_proba(logit(p_test_raw).reshape(-1, 1))[:, 1]
print(f"1,500 loans ({small.default_12m.sum()} defaults) to calibrate on:")
print(f"  isotonic: ECE {100 * ece(y_test, p_iso_s):.2f} pts, "
      f"{len(np.unique(np.round(p_iso_s, 6)))} distinct PD values, AUC {roc_auc_score(y_test, p_iso_s):.3f}")
print(f"  Platt:    ECE {100 * ece(y_test, p_platt_s):.2f} pts, AUC {roc_auc_score(y_test, p_platt_s):.3f}")

print("\n== Gotcha 3: AUC cannot see the problem ==")
print(f"AUC raw {roc_auc_score(y_test, p_test_raw):.3f} vs Platt "
      f"{roc_auc_score(y_test, methods['Platt scaling']):.3f}: same ranking, "
      f"average PD {100 * p_test_raw.mean():.2f}% vs {100 * methods['Platt scaling'].mean():.2f}%")

# ---------------------------------------------------------------------------
# 6. Visuals (house style: tools/viz_style.py)
# ---------------------------------------------------------------------------
FOOT = ("Synthetic data modelled on UK unsecured lending patterns and the UCI Default of Credit "
        "Card Clients dataset | Thamesgate Building Society is fictional | Data Explained #003")

# ---- chart_1 (context): what the credit risk manager saw
fig, ax = vs.figure(height=5.2)
x = np.arange(len(cohorts))
mat = cohorts.mature_share == 1
ax.plot(x[mat], 100 * cohorts.default_rate[mat], color=vs.INK_2, lw=2, marker="o", ms=4, zorder=3)
last_mat = np.where(mat)[0][-1]
imm = np.r_[last_mat, np.where(~mat)[0]]
ax.plot(x[imm], 100 * cohorts.default_rate.iloc[imm], color=vs.MUTED, lw=1.6, ls=(0, (3, 2)),
        marker="o", ms=3, zorder=3)
vs.shade(ax, last_mat + 0.5, len(cohorts) - 0.5, "Outcomes still\ncoming in")
x_app = len(cohorts) + 1.5
raw_avg = 100 * p_app_raw.mean()
ax.bar([x_app], [raw_avg], width=0.9, color=vs.SERIES[1], zorder=3)
ax.text(x_app, raw_avg + 0.25, f"{raw_avg:.1f}%", ha="center", fontsize=10, fontweight="bold",
        color=vs.INK)
vs.ref_line(ax, 100 * RISK_APPETITE, "Board risk\nappetite: 4.5%", color=vs.STATUS["critical"])
pk = mature_cohorts.default_rate.idxmax()
vs.callout(ax, pk, 100 * cohorts.default_rate[pk],
           f"Worst fully-observed quarter:\n{100 * cohorts.default_rate[pk]:.1f}% ({cohorts.quarter[pk]})",
           dx=-60, dy=60, marker_color=vs.INK_2)
ax.annotate("New model's average\npredicted default rate,\nJul-Sep 2026 applicants",
            (x_app - 0.45, raw_avg * 0.65), xytext=(-110, 0), textcoords="offset points",
            fontsize=8.5, color=vs.INK, ha="center", va="center",
            arrowprops=dict(arrowstyle="-", color=vs.INK_3, lw=0.8))
ax.set_xticks(list(x) + [x_app], [s.replace("Q", "\nQ") for s in cohorts.quarter] + ["2026\nQ3 apps"],
              fontsize=7.5)
ax.set_ylim(0, max(raw_avg + 2, 6))
ax.set_yticks(np.arange(0, ax.get_ylim()[1], 4))
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
vs.headline(fig, f"The new model says {raw_avg:.1f}% of applicants will default. "
            f"No quarter has gone above {100 * mature_cohorts.default_rate.max():.1f}%",
            "Thamesgate Building Society, personal loans: % defaulting within 12 months, by quarter "
            "the loan was drawn\nJan 2023 to Mar 2026 (grey), and the model's prediction for this "
            "quarter's applications (orange)")
vs.footer(fig, FOOT)
vs.save(fig, HERE / "chart_1.png")

# ---- chart_2 (explainer): reliability diagram, raw vs Platt, on the test set
fig, ax = vs.figure(height=5.8)
fig.subplots_adjust(right=0.86)
vs.style_axes(ax, grid="both")
lim = 100 * max(rel_raw.predicted.max(), rel_raw.observed.max()) * 1.08
ax.plot([0, lim], [0, lim], color=vs.INK_3, lw=1, ls="--", zorder=2)
ax.text(lim * 0.47, lim * 0.535, "Perfect calibration:\npredicted = actual", fontsize=8,
        color=vs.INK_2, ha="right", va="center")
ax.plot(100 * rel_raw.predicted, 100 * rel_raw.observed, color=vs.SERIES[1], lw=1.8, marker="o",
        ms=5, zorder=4)
ax.plot(100 * rel_platt.predicted, 100 * rel_platt.observed, color=vs.SERIES[0], lw=2.2,
        marker="o", ms=5, zorder=5)
top = rel_raw.iloc[-1]
vs.callout(ax, 100 * top.predicted, 100 * top.observed,
           f"Riskiest 10%: model said {100 * top.predicted:.1f}%,\n"
           f"actually {100 * top.observed:.1f}% defaulted", dx=-210, dy=62,
           marker_color=vs.SERIES[1])
tp = rel_platt.iloc[-1]
vs.callout(ax, 100 * tp.predicted, 100 * tp.observed,
           f"Calibrated (Platt scaling):\n{100 * tp.predicted:.1f}% predicted, {100 * tp.observed:.1f}% actual",
           dx=-150, dy=58, marker_color=vs.SERIES[0])
vs.end_label(ax, 100 * rel_raw.predicted.iloc[-1], 100 * rel_raw.observed.iloc[-1],
             "Raw model", color=vs.SERIES[1], dx=10)
ax.set_xlim(0, lim)
ax.set_ylim(0, lim * 0.6)
ax.set_xlabel("Predicted default rate (average for the group)", fontsize=8.5)
ax.set_ylabel("Actual default rate", fontsize=8.5)
ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
vs.headline(fig, "The raw model ranks risk well but its percentages run about "
            f"{p_test_raw.mean() / y_test.mean():.0f}x too high",
            f"Reliability curve: {len(test):,} test loans drawn Jul-Oct 2025, split into 10 equal-sized "
            "groups by predicted risk.\nEach dot is one group: predicted vs actual 12-month default rate")
vs.footer(fig, FOOT)
vs.save(fig, HERE / "chart_2.png")

# ---- chart_3 (results): options table with the business consequences
tbl = results.copy()
tbl["vs_actual"] = tbl.expected_loss_gbp_m / (realised_loss / 1e6) - 1
show = pd.DataFrame({
    "Method": tbl.method,
    "AUC": tbl.AUC,
    "Avg PD": tbl.avg_PD_pct,
    "Calibration error (pts)": tbl.ECE_pct,
    "Expected loss (£m)": tbl.expected_loss_gbp_m,
    "vs realised loss": 100 * tbl.vs_actual,
})
show.loc[len(show)] = ["Actual outcome", np.nan, 100 * y_test.mean(), np.nan,
                       realised_loss / 1e6, np.nan]
show_fmt = show.copy()
show_fmt["AUC"] = show.AUC.map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
show_fmt["Avg PD"] = show["Avg PD"].map(lambda v: f"{v:.2f}%")
show_fmt["Calibration error (pts)"] = show["Calibration error (pts)"].map(
    lambda v: "" if pd.isna(v) else f"{v:.2f}")
show_fmt["Expected loss (£m)"] = show["Expected loss (£m)"].map(lambda v: f"£{v:.2f}m")
show_fmt["vs realised loss"] = show["vs realised loss"].map(
    lambda v: "" if pd.isna(v) else f"{v:+.0f}%")
show_fmt = show_fmt.astype(str)
best = int(results.ECE_pct.idxmin())
vs.table_png(show_fmt, HERE / "chart_3.png",
             f"{results.method[best]} cuts calibration error from {results.ECE_pct[0]:.2f} to "
             f"{results.ECE_pct[best]:.2f} points, with the same AUC",
             f"Test set: {len(test):,} loans drawn Jul-Oct 2025, scored by the same model, outcomes "
             "known. AUC measures ranking;\ncalibration error is the average gap between predicted and "
             "actual default rate. Loss = PD x 75% LGD x loan amount",
             footer_text="Synthetic data | Thamesgate Building Society is fictional | Data Explained #003",
             highlight_rows=(best,), col_width=1.75)
print(f"\nLowest calibration error on test: {results.method[best]}")
print("\nSaved chart_1.png, chart_2.png, chart_3.png")
