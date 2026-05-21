"""
build_report.py
===============
Renders  images/dashboard_preview.png  (a static mock of the Power BI executive + campaign pages)
and      reports/executive_summary.pdf (4-page management summary)
from the processed tables produced by the notebooks.

    python src/build_report.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import FuncFormatter
from matplotlib.gridspec import GridSpec

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import viz  # noqa: E402

viz.setup()
plt.rcParams["text.parse_math"] = False   # dollar signs are currency, not TeX
P = ROOT / "data/processed"
cm = pd.read_csv(P / "campaign_metrics.csv", parse_dates=["campaign_date"])
cv = pd.read_csv(P / "customer_value.csv", parse_dates=["acquisition_date"])
o = pd.read_csv(P / "orders.csv", parse_dates=["order_date"])
stats_tbl = pd.read_csv(P / "stats_viral_vs_nonviral.csv", index_col=0)
kind = pd.read_csv(P / "stats_save_vs_share_led.csv")
perf = pd.read_csv(P / "model_performance.csv", index_col=0)
big = cm[cm.new_customers >= 30]


def pooled(d):
    n = d.new_customers.sum()
    return dict(spend=d.spend.sum(), customers=n, cac=d.spend.sum() / n, roas=d.revenue_7d.sum() / d.spend.sum(),
                repeat=(d.repeat_90d * d.new_customers).sum() / n, ltv=d.cm_90d_total.sum() / n,
                ltv_cac=d.cm_90d_total.sum() / d.spend.sum(), profit=d.cm_90d_total.sum() - d.spend.sum())


ALL, NV, VI = pooled(cm), pooled(cm[cm.is_viral == 0]), pooled(cm[cm.is_viral == 1])
A = big[big.is_viral == 1].sort_values("share_rate", ascending=False).iloc[0]
B = big.sort_values("ltv_cac", ascending=False).iloc[0]
C = big[big.is_viral == 1].sort_values("ltv_cac", ascending=False).iloc[0]


# --------------------------------------------------------------------------------------
def kpi(ax, label, value, sub=None):
    ax.axis("off")
    ax.text(0, 0.72, label.upper(), fontsize=7.5, color=viz.MUTED, weight="bold", transform=ax.transAxes)
    ax.text(0, 0.28, value, fontsize=17, color=viz.INK, weight="bold", transform=ax.transAxes)
    if sub:
        ax.text(0, 0.02, sub, fontsize=7.5, color=viz.INK2, transform=ax.transAxes)


def bubble(ax, annotate=True):
    for flag, col, lbl in [(0, viz.NONVIRAL, "Non-viral"), (1, viz.VIRAL, "Viral")]:
        d = big[big.is_viral == flag]
        ax.scatter(d.virality_score, d.cm_90d_per_customer, s=np.sqrt(d.new_customers) * 5, color=col, alpha=0.65,
                   label=lbl, edgecolor=viz.SURFACE, linewidth=0.8)
    if annotate:
        for _, r in big[big.is_viral == 1].iterrows():
            ax.annotate(r.campaign_id, (r.virality_score, r.cm_90d_per_customer), fontsize=6.5, xytext=(6, 0), textcoords="offset points", color=viz.INK2)
    ax.axhline(big.cm_90d_per_customer.median(), color=viz.MUTED, linestyle=":", linewidth=1)
    ax.yaxis.set_major_formatter(FuncFormatter(viz.money)); ax.set_xlabel("virality score"); ax.set_ylabel("90-day CM-LTV / customer")
    ax.set_title("Campaign virality vs customer value (bubble = customers)"); ax.legend(loc="upper left", fontsize=8)


def dashboard():
    fig = plt.figure(figsize=(15, 9.2))
    gs = GridSpec(4, 4, figure=fig, height_ratios=[0.55, 1.3, 1.3, 0.05], hspace=0.55, wspace=0.3)
    fig.text(0.02, 0.965, "Viral to Value — Executive overview", fontsize=16, weight="bold", color=viz.INK)
    fig.text(0.02, 0.94, "Simulated Gen-Z DTC brand · 120 Instagram campaigns · Jan–Sep 2025 · 90-day customer economics", fontsize=9, color=viz.INK2)
    cards = [("Marketing spend", f"${ALL['spend']/1e6:.2f}M"), ("Customers acquired", f"{ALL['customers']:,}"),
             ("Blended CAC", f"${ALL['cac']:.0f}", f"viral ${VI['cac']:.0f} · non-viral ${NV['cac']:.0f}"),
             ("90-day CM-LTV", f"${ALL['ltv']:.0f}", f"viral ${VI['ltv']:.0f} · non-viral ${NV['ltv']:.0f}"),
             ]
    for i, c in enumerate(cards):
        kpi(fig.add_subplot(gs[0, i]), *c)
    ax = fig.add_subplot(gs[1:3, 0:2]); bubble(ax)
    ax = fig.add_subplot(gs[1, 2])
    labels = ["Non-viral", "Viral"]; ax.bar(labels, [NV["ltv_cac"], VI["ltv_cac"]], color=[viz.NONVIRAL, viz.VIRAL], width=0.55)
    ax.axhline(1, color=viz.BAD, linestyle="--", linewidth=1); ax.set_title("LTV:CAC (pooled)")
    for i, v in enumerate([NV["ltv_cac"], VI["ltv_cac"]]): ax.text(i, v + 0.05, f"{v:.2f}×", ha="center", fontsize=9)
    ax = fig.add_subplot(gs[1, 3])
    ax.bar(labels, [NV["repeat"], VI["repeat"]], color=[viz.NONVIRAL, viz.VIRAL], width=0.55); ax.yaxis.set_major_formatter(FuncFormatter(viz.pct)); ax.set_title("90-day repeat rate")
    for i, v in enumerate([NV["repeat"], VI["repeat"]]): ax.text(i, v + 0.005, f"{v:.0%}", ha="center", fontsize=9)
    ax = fig.add_subplot(gs[2, 2:4])
    d = big.sort_values("ltv_cac", ascending=False).reset_index(drop=True)
    ax.bar(d.index, d.ltv_cac.clip(upper=12), color=[viz.VIRAL if v else viz.NONVIRAL for v in d.is_viral], width=0.85)
    ax.axhline(1, color=viz.BAD, linestyle="--", linewidth=1); ax.axhline(3, color=viz.GOOD, linestyle="--", linewidth=1)
    ax.set_xticks([]); ax.set_title("LTV:CAC by campaign (orange = viral); lines at 1× and 3×"); ax.set_ylabel("LTV : CAC")
    fig.text(0.02, 0.015, "Static preview of the Power BI report (see powerbi/README.md). Simulated data — docs/methodology.md.", fontsize=7.5, color=viz.MUTED)
    fig.savefig(ROOT / "images/dashboard_preview.png", dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------------------------
def para(fig, y, text, size=9, color=viz.INK, weight="normal", x=0.07, wrap=118):
    import textwrap
    lines = []
    for block in text.split("\n"):
        lines += textwrap.wrap(block, wrap) if block.strip() else [""]
    for ln in lines:
        fig.text(x, y, ln, fontsize=size, color=color, weight=weight, va="top")
        y -= size * 0.0022
    return y - 0.012


def page_header(fig, title, n):
    fig.text(0.07, 0.95, title, fontsize=14, weight="bold", color=viz.INK)
    fig.text(0.93, 0.975, f"Viral to Value · executive summary · {n}/4", fontsize=7.5, color=viz.MUTED, ha="right")
    fig.add_artist(plt.Line2D([0.07, 0.93], [0.935, 0.935], color="#e6e5e1", linewidth=1))


def report():
    v_diff = stats_tbl.loc["90-day CM-LTV ($)"]
    rep_diff = stats_tbl.loc["90-day repeat rate"]
    kind_nv = kind[kind.is_viral.astype(str).str.contains("Non")].set_index("virality_kind")
    with PdfPages(ROOT / "reports/executive_summary.pdf") as pdf:
        # ---- page 1: the answer ---------------------------------------------------------
        fig = plt.figure(figsize=(8.27, 11.69)); page_header(fig, "Do viral Instagram campaigns create durable customers?", 1)
        y = 0.90
        y = para(fig, y, "Executive summary — simulated Gen-Z DTC streetwear brand, 120 Instagram campaigns (Jan–Sep 2025), "
                         f"{ALL['customers']:,} acquired customers, 90-day customer economics.", 9, viz.INK2)
        y = para(fig, y, "THE SHORT ANSWER", 9, viz.MUTED, "bold")
        y = para(fig, y,
                 f"Virality is neither the problem nor the solution. Viral campaigns acquire customers far more cheaply "
                 f"(CAC ${VI['cac']:.0f} vs ${NV['cac']:.0f}) and post better first-week ROAS ({VI['roas']:.1f}× vs {NV['roas']:.1f}×), "
                 f"but each viral customer is worth slightly less over 90 days (CM-LTV ${VI['ltv']:.0f} vs ${NV['ltv']:.0f}; "
                 f"90-day repeat {VI['repeat']:.0%} vs {NV['repeat']:.0%}). Pooled, viral campaigns still beat non-viral ones on LTV:CAC "
                 f"({VI['ltv_cac']:.2f}× vs {NV['ltv_cac']:.2f}×).\n"
                 f"\nThe gap between viral and non-viral customers is small (Cliff's δ = {v_diff['Cliff\'s δ']:.2f}) and mostly disappears once "
                 "we control for what the campaign offered: discount depth, creator tier, first-order experience and product. "
                 "The spread WITHIN the eight viral campaigns (90-day CM-LTV from $28 to $82 per customer) is far larger than the "
                 "gap BETWEEN viral and non-viral.")
        y = para(fig, y, "WHAT SEPARATES PROFITABLE VIRALITY FROM VANITY VIRALITY", 9, viz.MUTED, "bold")
        y = para(fig, y,
                 "1. Saves beat shares. Campaign save rate is the strongest engagement predictor of customer value (+$12 of 90-day "
                 "CM-LTV per +1 pt of save rate); share rate is negatively correlated and adds nothing once save rate is known. "
                 f"Across the portfolio, save-led campaigns produce customers worth ${kind_nv.loc['save-led', 'cm_ltv_90d'] - kind_nv.loc['share-led', 'cm_ltv_90d']:.0f} more than share-led ones.\n"
                 "2. Discounts buy the spike and lose the customer. Each point of first-order discount removes about $1.30 of 90-day "
                 "CM-LTV; 20–30% campaigns repeat at 29% vs 47% for full-price campaigns.\n"
                 "3. Trusted creators over big creators. Micro/Mid-tier cohorts repeat at 42–46%; Macro at 32%. Macro campaigns "
                 "lost money at 90 days in aggregate and Mega campaigns only broke even.\n"
                 "4. Reach itself is irrelevant to value. Controlling for the above, log reach has no significant effect on CM-LTV.")
        y = para(fig, y, "RECOMMENDATION", 9, viz.MUTED, "bold")
        y = para(fig, y,
                 "Keep chasing reach — but only with content built to be saved (product-led Reels and carousels, drops, UGC) and "
                 "without deep discount codes. Judge campaigns on 90-day LTV:CAC and payback, not on views or first-week ROAS. "
                 f"Roughly half of all campaigns ({(big.ltv_cac < 1).mean():.0%}) have not paid back at 90 days; that is a budget "
                 "problem, and it is not a viral-vs-non-viral problem. Reallocating the bottom-quartile LTV:CAC budget "
                 "toward the save-led, full-price profile is the single largest lever in the portfolio.")
        h = max(y - 0.10, 0.16)
        ax = fig.add_axes([0.1, 0.05, 0.8, h]); bubble(ax, annotate=False)
        pdf.savefig(fig); plt.close(fig)

        # ---- page 2: campaign A / B / C ----------------------------------------------
        fig = plt.figure(figsize=(8.27, 11.69)); page_header(fig, "Three campaigns, three lessons", 2)
        y = 0.90
        y = para(fig, y, "A — the most-shared campaign of the year. B — the best 90-day economics. C — viral AND valuable.", 9, viz.INK2)
        rows = [("Type / content / creator", lambda r: f"{r.campaign_type} · {r.content_type} · {r.creator_tier}"),
                ("Discount offered", lambda r: f"{r.discount_pct:.0f}%"), ("Reach", lambda r: f"{r.reach/1e6:.1f}M"),
                ("Share rate / save rate", lambda r: f"{r.share_rate:.2%} / {r.save_rate:.2%}"), ("Spend", lambda r: f"${r.spend:,.0f}"),
                ("New customers", lambda r: f"{r.new_customers:,}"), ("CAC", lambda r: f"${r.cac:.0f}"),
                ("First-week revenue / ROAS", lambda r: f"${r.revenue_7d:,.0f} / {r.roas_7d:.1f}×"),
                ("90-day repeat", lambda r: f"{r.repeat_90d:.0%}"), ("90-day CM-LTV / customer", lambda r: f"${r.cm_90d_per_customer:.0f}"),
                ("LTV : CAC", lambda r: f"{r.ltv_cac:.2f}×"), ("90-day profit", lambda r: f"${r.campaign_profit_90d:,.0f}"),
                ("Payback (days)", lambda r: "never (≤180d)" if np.isnan(r.payback_days) else f"{r.payback_days:.0f}")]
        ax = fig.add_axes([0.07, 0.42, 0.86, 0.44]); ax.axis("off")
        tbl = ax.table(cellText=[[lbl, f(A), f(B), f(C)] for lbl, f in rows],
                       colLabels=["", f"A · {A.campaign_id}", f"B · {B.campaign_id}", f"C · {C.campaign_id}"], loc="upper center", cellLoc="center", colLoc="center")
        tbl.auto_set_font_size(False); tbl.set_fontsize(8.5); tbl.scale(1, 1.5)
        for (r, c_), cell in tbl.get_celld().items():
            cell.set_edgecolor("#e6e5e1")
            if r == 0: cell.set_text_props(weight="bold", color=viz.INK); cell.set_facecolor("#f1f0ec")
            if c_ == 0: cell.set_text_props(ha="left", color=viz.INK2)
        y = 0.40
        y = para(fig, y,
                 f"Campaign A ({A.campaign_type}, {A.discount_pct:.0f}% off) was forwarded {A.shares:,} times and reached {A.reach/1e6:.1f}M accounts. "
                 f"It converted {A.new_customers:,} customers who mostly bought once, at a discount, and did not return: 90-day repeat {A.repeat_90d:.0%}, "
                 f"LTV:CAC {A.ltv_cac:.1f}×. It is the textbook vanity spike.\n\n"
                 f"Campaign B ({B.campaign_type}, {B.creator_tier} creator) reached a fraction of A's audience but was saved {B.saves:,} times. "
                 f"It repeats at {B.repeat_90d:.0%} and returns {B.ltv_cac:.1f}× its CAC in 90 days.\n\n"
                 f"Campaign C ({C.campaign_type} {C.content_type}) shows that scale and value are compatible: it is one of the eight viral "
                 f"campaigns by reach and sharing, yet its save rate is the highest in the portfolio. Result: {C.new_customers:,} customers, "
                 f"{C.repeat_90d:.0%} repeat, LTV:CAC {C.ltv_cac:.1f}×, and the largest 90-day profit of any campaign (${C.campaign_profit_90d:,.0f}).\n\n"
                 "The difference between A and C is not how far the content travelled. It is what the audience did with it and what the offer was.")
        pdf.savefig(fig); plt.close(fig)

        # ---- page 3: evidence ----------------------------------------------------------
        fig = plt.figure(figsize=(8.27, 11.69)); page_header(fig, "Evidence: cohorts, statistics, drivers", 3)
        ax = fig.add_axes([0.1, 0.66, 0.36, 0.22])
        x = np.arange(3); w = 0.36
        for i, (flag, col, lbl) in enumerate([(0, viz.NONVIRAL, "Non-viral"), (1, viz.VIRAL, "Viral")]):
            d = cv[cv.is_viral == flag]; vals = [d.repeat_30d.mean(), d.repeat_60d.mean(), d.repeat_90d.mean()]
            ax.bar(x + (i - 0.5) * w, vals, w, color=col, label=lbl)
        ax.set_xticks(x); ax.set_xticklabels(["30d", "60d", "90d"]); ax.yaxis.set_major_formatter(FuncFormatter(viz.pct)); ax.set_title("Repeat-purchase rate"); ax.legend(fontsize=7)
        ax = fig.add_axes([0.56, 0.66, 0.36, 0.22])
        oc = o.merge(cv[["customer_id", "is_viral", "acquisition_date"]], on="customer_id"); oc["d"] = (oc.order_date - oc.acquisition_date).dt.days
        for flag, col, lbl in [(0, viz.NONVIRAL, "Non-viral"), (1, viz.VIRAL, "Viral")]:
            d = oc[oc.is_viral == flag]; n = (cv.is_viral == flag).sum()
            cum = d.groupby("d").contribution_margin.sum().reindex(range(0, 181), fill_value=0).cumsum() / n
            ax.plot(cum.index, cum.values, color=col, label=lbl)
        ax.axvline(90, color=viz.MUTED, linestyle=":"); ax.yaxis.set_major_formatter(FuncFormatter(viz.money)); ax.set_title("Cumulative CM per customer"); ax.set_xlabel("days since acquisition"); ax.legend(fontsize=7)
        ax = fig.add_axes([0.1, 0.36, 0.82, 0.22])
        by = cm.assign(band=pd.cut(cm.discount_pct, [-1, 0, 15, 30], labels=["no discount", "10–15%", "20–30%"])).groupby("band").apply(lambda d: pd.Series(pooled(d)))
        ax.bar(by.index.astype(str), by.ltv, color=viz.SERIES[0], width=0.5); ax.yaxis.set_major_formatter(FuncFormatter(viz.money)); ax.set_title("90-day CM-LTV per customer by campaign discount")
        for i, v in enumerate(by.ltv): ax.text(i, v + 1, f"${v:.0f}  (repeat {by.repeat.iloc[i]:.0%})", ha="center", fontsize=8)
        y = 0.31
        y = para(fig, y, "STATISTICAL TESTS (customer level, n = 40,947)", 9, viz.MUTED, "bold")
        y = para(fig, y,
                 f"• 90-day CM-LTV, viral − non-viral: ${v_diff['diff (viral − non)']:.2f} (bootstrap 95% CI {v_diff['95% CI low']:.2f} to {v_diff['95% CI high']:.2f}); "
                 f"Mann–Whitney p = {v_diff['MWU p']:.3f}; Cliff's δ = {v_diff['Cliff\'s δ']:.3f} (negligible).\n"
                 f"• 90-day repeat, viral − non-viral: {rep_diff['diff (viral − non)']*100:.1f} pts (95% CI {rep_diff['95% CI low']*100:.1f} to {rep_diff['95% CI high']*100:.1f}); χ² p < 0.001; Cramér's V = 0.05.\n"
                 "• Logistic regression: odds ratio for is_viral = 0.77 alone, 0.91 with discount, creator tier, first-order refund/late delivery, value and category as controls.\n"
                 "• Campaign-level weighted OLS (n = 100, R² = 0.54): save rate +$12.5/pt (p < 0.001), discount −$1.26/pt (p < 0.001); log reach and share rate not significant.\n"
                 f"• Early-signal model (day-7 features, time-based holdout): ROC-AUC {perf['ROC-AUC'].max():.2f}; top-scored 20% of new customers repeat at 1.6× the base rate "
                 "and hold ~38% of 90-day margin. Campaign virality features add < 0.01 AUC.")
        pdf.savefig(fig); plt.close(fig)

        # ---- page 4: method & caveats -----------------------------------------------
        fig = plt.figure(figsize=(8.27, 11.69)); page_header(fig, "Method, definitions and caveats", 4)
        y = 0.90
        y = para(fig, y, "DEFINITIONS", 9, viz.MUTED, "bold")
        y = para(fig, y,
                 "Viral = reach ≥ 90th percentile AND share rate (shares ÷ reach) ≥ 75th percentile of the 120 campaigns; 8 campaigns qualify. "
                 "Contribution margin = net revenue − COGS − shipping − payment fees − refunds. 90-day CM-LTV = contribution margin from a customer's "
                 "orders in the 90 days after acquisition. CAC = campaign spend ÷ customers acquired. LTV:CAC = 90-day CM-LTV ÷ CAC. "
                 "7-day ROAS = cohort net revenue in the 7 days after the campaign ÷ spend. Attribution is last-touch to the acquiring campaign.")
        y = para(fig, y, "DATA", 9, viz.MUTED, "bold")
        y = para(fig, y,
                 "This project uses a simulated DTC e-commerce dataset designed to reproduce realistic customer acquisition, campaign, transaction, "
                 "retention and profitability behaviour. Results describe the simulated business and are not empirical claims about Instagram users generally. "
                 "Crucially, the simulator contains no 'viral ⇒ bad customer' rule: virality only scales reach, traffic and volume, while customer quality "
                 "depends on discount, content intent, creator tier, first-order experience, product and noise. Every finding above had to be discovered, "
                 "not assumed (docs/methodology.md, docs/assumptions.md).")
        y = para(fig, y, "CAVEATS", 9, viz.MUTED, "bold")
        y = para(fig, y,
                 "• Only 8 viral campaigns: within-viral comparisons are directional; customer-level tests are well powered.\n"
                 "• LTV is truncated at 90 days; long-lived customers are undervalued uniformly.\n"
                 "• Discounts are treated as revenue reduction, not spend, so CAC flatters discount campaigns and CM-LTV carries the cost.\n"
                 "• The reallocation scenario assumes CAC does not rise with scale — an upper bound.\n"
                 "• One random seed; re-simulating changes the numbers but not the mechanism.")
        y = para(fig, y, "REPOSITORY", 9, viz.MUTED, "bold")
        y = para(fig, y, "notebooks/01–07 (quality → EDA → campaigns → cohorts → profitability → statistics → model), sql/ (PostgreSQL, run on DuckDB), "
                         "src/ (generator, cleaning, metrics, features), powerbi/ (model, DAX, extracts), docs/.")
        pdf.savefig(fig); plt.close(fig)


if __name__ == "__main__":
    dashboard()
    report()
    print("wrote images/dashboard_preview.png and reports/executive_summary.pdf")
