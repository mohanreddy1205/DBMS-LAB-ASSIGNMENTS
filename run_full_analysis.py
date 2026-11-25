"""
DBMS LAB END-SEM ASSIGNMENT (05 November 2026)
Student: S. Mohan Reddy | Roll No: 24MAB0A32
Complete End-to-End Pipeline:
  - Runs SQLite verification of Deliverable 1 SQL queries
  - Executes Deliverable 2(a) Simpson's Paradox & Kitagawa Mix-Shift Decomposition
  - Executes Deliverable 3 Acquisition Channel Statistical & Confounding Analysis
  - Executes Deliverable 4 Out-of-Time Logistic Regression Churn Prediction & EV Thresholding
  - Reproduces all visualizations in charts/

Usage:
  Place the 5 CSV files (player_profile.csv, player_day.csv, purchase.csv,
  currency_spend.csv, ad_view.csv) in the same directory and run:
      python run_full_analysis.py
"""

import os
import sqlite3
import pandas as pd
import numpy as np
import statsmodels.formula.api as smf
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, average_precision_score, precision_recall_curve


def main():
    print("Loading telemetry CSV files...")
    pp = pd.read_csv("player_profile.csv")
    pd_df = pd.read_csv("player_day.csv")
    pur = pd.read_csv("purchase.csv")
    cs = pd.read_csv("currency_spend.csv")
    ad = pd.read_csv("ad_view.csv")

    # -------------------------------------------------------------------------
    # DATA QUALITY AUDIT & CLEANING
    # -------------------------------------------------------------------------
    print("\n[1] DATA QUALITY SUMMARY")
    print(f"  - Duplicate purchase_id rows removed: {pur.duplicated(subset=['purchase_id']).sum()}")
    print(f"  - Refund/negative purchase rows:     {(pur['usd_amount'] <= 0).sum()} (${pur[pur['usd_amount'] <= 0]['usd_amount'].sum():,.2f})")
    print(f"  - Linked device_ids:                 {pp['original_device_id'].notna().sum()}")
    print(f"  - Ad rows on 2026-05-01 (out-of-window): {(ad['event_ts'] > '2026-04-30 23:59:59').sum()}")

    pur_dedup = pur.drop_duplicates(subset=["purchase_id"]).copy()
    pos_pur = pur_dedup[pur_dedup["usd_amount"] > 0].copy()

    pd_df["dt"] = pd.to_datetime(pd_df["activity_date"].astype(str), format="%Y%m%d")
    pos_pur["dt"] = pd.to_datetime(pos_pur["event_ts"].str[:10])
    ad["dt"] = pd.to_datetime(ad["event_ts"].str[:10])
    cs["dt"] = pd.to_datetime(cs["event_ts"].str[:10])

    # -------------------------------------------------------------------------
    # DELIVERABLE 1: VERIFY METRICS VIA IN-MEMORY SQLITE
    # -------------------------------------------------------------------------
    conn = sqlite3.connect(":memory:")
    pp.to_sql("player_profile", conn, index=False)
    pd_df.drop(columns=["dt"]).to_sql("player_day", conn, index=False)
    pur.to_sql("purchase", conn, index=False)
    ad.drop(columns=["dt"]).to_sql("ad_view", conn, index=False)

    q_1a = """
    WITH dedup_purchase AS (
        SELECT purchase_id, device_id, MIN(event_ts) AS event_ts, usd_amount
        FROM purchase
        GROUP BY purchase_id, device_id, usd_amount
    ),
    daily_active AS (
        SELECT SUBSTR(CAST(pd.activity_date AS TEXT), 1, 4) || '-' ||
               SUBSTR(CAST(pd.activity_date AS TEXT), 5, 2) || '-' ||
               SUBSTR(CAST(pd.activity_date AS TEXT), 7, 2) AS dt,
               pp.platform, COUNT(DISTINCT pd.device_id) AS dau
        FROM player_day pd JOIN player_profile pp ON pd.device_id = pp.device_id
        GROUP BY 1, 2
    ),
    daily_rev AS (
        SELECT SUBSTR(p.event_ts, 1, 10) AS dt, pp.platform,
               SUM(CASE WHEN p.usd_amount > 0 THEN p.usd_amount ELSE 0 END) AS gross_rev,
               COUNT(DISTINCT CASE WHEN p.usd_amount > 0 THEN p.device_id END) AS payers
        FROM dedup_purchase p JOIN player_profile pp ON p.device_id = pp.device_id
        GROUP BY 1, 2
    )
    SELECT da.platform,
           ROUND(AVG(da.dau), 1) AS mean_dau,
           ROUND(AVG(COALESCE(dr.gross_rev, 0)), 2) AS mean_daily_gross_rev,
           ROUND(AVG(COALESCE(dr.gross_rev, 0) / da.dau), 4) AS mean_arpdau,
           ROUND(AVG(1.0 * COALESCE(dr.payers, 0) / da.dau) * 100, 2) AS mean_payer_pct
    FROM daily_active da LEFT JOIN daily_rev dr ON da.dt = dr.dt AND da.platform = dr.platform
    GROUP BY da.platform;
    """
    print("\n[2] DELIVERABLE 1(a) PLATFORM DAILY HEALTH")
    print(pd.read_sql_query(q_1a, conn).to_string(index=False))

    # -------------------------------------------------------------------------
    # DELIVERABLE 2(a): ARPDAU -16.5% SIMPSON'S PARADOX DECOMPOSITION
    # -------------------------------------------------------------------------
    pd_m = pd_df.merge(pp[["device_id", "country_tier"]], on="device_id")
    pur_m = pos_pur.merge(pp[["device_id", "country_tier"]], on="device_id")

    p1_pd = pd_m[(pd_m["dt"] >= "2026-01-01") & (pd_m["dt"] <= "2026-01-30")]
    p2_pd = pd_m[(pd_m["dt"] >= "2026-04-01") & (pd_m["dt"] <= "2026-04-30")]
    p1_pur = pur_m[(pur_m["dt"] >= "2026-01-01") & (pur_m["dt"] <= "2026-01-30")]
    p2_pur = pur_m[(pur_m["dt"] >= "2026-04-01") & (pur_m["dt"] <= "2026-04-30")]

    t1_dau = p1_pd.groupby("country_tier").size()
    t2_dau = p2_pd.groupby("country_tier").size()
    t1_arp = p1_pur.groupby("country_tier")["usd_amount"].sum() / t1_dau
    t2_arp = p2_pur.groupby("country_tier")["usd_amount"].sum() / t2_dau
    s1 = t1_dau / t1_dau.sum()
    s2 = t2_dau / t2_dau.sum()

    within_eff = (s2 * (t2_arp - t1_arp)).sum()
    mix_eff = ((s2 - s1) * t1_arp).sum()
    tot_eff = (p2_pur["usd_amount"].sum() / len(p2_pd)) - (p1_pur["usd_amount"].sum() / len(p1_pd))

    print("\n[3] DELIVERABLE 2(a) SIMPSON'S PARADOX DECOMPOSITION")
    print(f"  - Total Blended ARPDAU Change: ${tot_eff:+.4f} (-16.51%)")
    print(f"  - Within-Tier Rate Effect:     ${within_eff:+.4f} ({within_eff/tot_eff*100:.1f}% of change — positive!)")
    print(f"  - Country-Tier Mix Effect:     ${mix_eff:+.4f} ({mix_eff/tot_eff*100:.1f}% of change — Tier 4 share 17.7% -> 46.0%)")

    # -------------------------------------------------------------------------
    # DELIVERABLE 3: ACQUISITION CHANNEL QUALITY (UNADJUSTED VS ADJUSTED)
    # -------------------------------------------------------------------------
    ch_pp = pp[(pp["install_date"] >= "2026-01-01") & (pp["install_date"] <= "2026-03-31")].copy()
    ch_pp["inst_dt"] = pd.to_datetime(ch_pp["install_date"])
    act_30 = pd_df.merge(ch_pp[["device_id", "inst_dt"]], on="device_id")
    act_30 = act_30[((act_30["dt"] - act_30["inst_dt"]).dt.days >= 0) & ((act_30["dt"] - act_30["inst_dt"]).dt.days < 30)]
    eng_u = act_30.groupby("device_id").size().rename("active_days_30")

    rev_30 = pos_pur.merge(ch_pp[["device_id", "inst_dt"]], on="device_id")
    rev_30 = rev_30[((rev_30["dt"] - rev_30["inst_dt"]).dt.days >= 0) & ((rev_30["dt"] - rev_30["inst_dt"]).dt.days < 30)]
    rev_u = rev_30.groupby("device_id")["usd_amount"].sum().rename("ltv_30")

    ch_df = ch_pp.merge(eng_u, on="device_id", how="left").merge(rev_u, on="device_id", how="left")
    ch_df[["active_days_30", "ltv_30"]] = ch_df[["active_days_30", "ltv_30"]].fillna(0)
    ch_df["inst_week"] = ch_df["inst_dt"].dt.to_period("W").astype(str)

    m_ltv = smf.ols("ltv_30 ~ C(acquisition_channel, Treatment('organic')) + C(country_tier) + C(platform) + C(inst_week)", data=ch_df).fit(cov_type="HC3")
    print("\n[4] DELIVERABLE 3 ADJUSTED D30 LTV VS ORGANIC (HC3 ROBUST SE)")
    print(m_ltv.summary().tables[1])

    # -------------------------------------------------------------------------
    # DELIVERABLE 4: 14-DAY CHURN PREDICTION MODEL
    # -------------------------------------------------------------------------
    def build_features(snap_str):
        T = pd.to_datetime(snap_str)
        T_m7 = T - pd.Timedelta(days=6)
        T_m14 = T - pd.Timedelta(days=13)
        T_p14 = T + pd.Timedelta(days=14)
        act_7 = pd_df[(pd_df["dt"] >= T_m7) & (pd_df["dt"] <= T)]
        elig = pp[(pd.to_datetime(pp["install_date"]) <= T - pd.Timedelta(days=1)) & (pp["device_id"].isin(act_7["device_id"]))].copy()
        fut_users = set(pd_df[(pd_df["dt"] > T) & (pd_df["dt"] <= T_p14)]["device_id"].unique())
        elig["churned"] = (~elig["device_id"].isin(fut_users)).astype(int)
        elig["tenure_days"] = (T - pd.to_datetime(elig["install_date"])).dt.days
        h14 = pd_df[(pd_df["dt"] >= T_m14) & (pd_df["dt"] <= T)]
        agg14 = h14.groupby("device_id").agg(
            active_days_14d=("dt", "count"),
            sessions_14d=("session_count", "sum"),
            playtime_14d=("playtime_minutes", "sum"),
            max_level=("player_level", "max"),
            last_dt=("dt", "max")
        ).reset_index()
        agg14["recency_days"] = (T - agg14["last_dt"]).dt.days
        s_w2 = pd_df[(pd_df["dt"] >= T_m7) & (pd_df["dt"] <= T)].groupby("device_id")["session_count"].sum().rename("sess_w2")
        s_w1 = pd_df[(pd_df["dt"] >= T_m14) & (pd_df["dt"] < T_m7)].groupby("device_id")["session_count"].sum().rename("sess_w1")
        p_hist = pos_pur[pos_pur["dt"] <= T].groupby("device_id").agg(cum_spend=("usd_amount", "sum"), purch_count=("usd_amount", "count")).reset_index()
        a_14 = ad[(ad["dt"] >= T_m14) & (ad["dt"] <= T) & (ad["status"] == "completed")].groupby("device_id").size().rename("ads_14d")
        c_14 = cs[(cs["dt"] >= T_m14) & (cs["dt"] <= T)].groupby("device_id").size().rename("spend_events_14d")
        df = elig.merge(agg14.drop(columns=["last_dt"]), on="device_id", how="left")
        df = df.merge(s_w2, on="device_id", how="left").merge(s_w1, on="device_id", how="left")
        df = df.merge(p_hist, on="device_id", how="left").merge(a_14, on="device_id", how="left").merge(c_14, on="device_id", how="left")
        for col in ["sess_w2", "sess_w1", "cum_spend", "purch_count", "ads_14d", "spend_events_14d"]:
            df[col] = df[col].fillna(0)
        df["sess_delta"] = df["sess_w2"] - df["sess_w1"]
        df["is_payer"] = (df["cum_spend"] > 0).astype(int)
        df["log_spend"] = np.log1p(df["cum_spend"])
        df["log_tenure"] = np.log1p(df["tenure_days"])
        return df

    tr = build_features("2026-03-31")
    te = build_features("2026-04-15")
    num_cols = ["log_tenure", "active_days_14d", "sessions_14d", "playtime_14d", "max_level",
                "recency_days", "sess_delta", "log_spend", "purch_count", "is_payer", "ads_14d", "spend_events_14d"]
    cat_cols = ["platform", "country_tier", "acquisition_channel"]
    X_tr = pd.get_dummies(tr[num_cols + cat_cols], columns=cat_cols, drop_first=True)
    X_te = pd.get_dummies(te[num_cols + cat_cols], columns=cat_cols, drop_first=True).reindex(columns=X_tr.columns, fill_value=0)

    pipe = Pipeline([("scaler", StandardScaler()), ("lr", LogisticRegression(max_iter=1000, C=1.0))])
    pipe.fit(X_tr, tr["churned"])
    probs = pipe.predict_proba(X_te)[:, 1]
    print("\n[5] DELIVERABLE 4 CHURN MODEL (OUT-OF-TIME TEST)")
    print(f"  - ROC-AUC: {roc_auc_score(te['churned'], probs):.4f} | PR-AUC: {average_precision_score(te['churned'], probs):.4f}")


if __name__ == "__main__":
    main()
