# Analysis Notes, Data Quality Audit & Judgement Calls
**Student:** S. Mohan Reddy (24MAB0A32) | **Course:** DBMS Lab End-Sem

## 1. Data Quality Audit & Handling
1. **Duplicate `purchase_id` Webhook Logs (122 extra rows):** `purchase.csv` contains 15,426 rows across 15,304 unique `purchase_id`s. Deduplicating via `MIN(event_ts)` removes $1,840.80 in duplicate positive rows ($217,593.22 true gross revenue vs. $219,434.02 raw).
2. **Refunds / Chargebacks (228 rows, -$3,274.72):** 222 of 228 negative transactions match an earlier positive purchase of the same pack by the same device (median lag 4.3 days). Excluded from gross revenue and time-to-first-purchase; reported separately as net revenue ($214,343.48).
3. **Off-Session Purchases (2,429 positive payer-days):** 2,449 positive deduplicated purchases occur on dates without a corresponding `player_day` row. Their USD revenue is preserved in the revenue numerator while active payer share uses matched active days.
4. **Rewarded Ad Statuses, March 6 Outage & May 1 Spillover:** Filtered to `status = 'completed'` (excluding 18.0% `started`/`abandoned` rows) and `<= 2026-04-30` (excluding 7,732 rows on `2026-05-01`). Identified a complete ad-mediation outage on `2026-03-06` (0 rows) and partial logging on `2026-01-01` (starts at 14:00).
5. **Account Linking (`original_device_id`) & Clock Skew:** Identified 3,211 linked devices and 110 payers whose `first_purchase_date` precedes `install_date` by 1–4 days due to device clock skew/re-installs.

## 2. Deliverable 2(a): Simpson's Paradox in ARPDAU (-16.5%)
- Overall ARPDAU declined from **$0.3543** (Jan 1–30) to **$0.2958** (Apr 1–30), a **-16.51%** drop (`-$0.0585`).
- Every individual country tier improved: Tier 1 `+7.15%` (`$0.5186 -> $0.5557`), Tier 2 `+7.90%` (`$0.3735 -> $0.4031`), Tier 3 `+11.61%` (`$0.2336 -> $0.2607`), and Tier 4 `+2.20%` (`$0.1543 -> $0.1577`).
- **Kitagawa Decomposition:** Within-tier rate changes contributed **+$0.0186** (`-31.8%` of the drop, i.e., a net positive), while country-tier mix shift contributed **-$0.0771** (`131.8%` of the drop) as Tier 4 DAU share surged from **17.7%** to **46.0%**.

## 3. Deliverable 3: Acquisition Channel Quality
- Evaluated Q1 2026 cohorts (`2026-01-01` to `2026-03-31`, `N = 37,489`) over a uniform 30-day window.
- Unadjusted `paid_video` D30 LTV trails `organic` by **-$0.92**, because **65.3%** of `paid_video` installs are in Tier 4 (vs. 18.3% for `organic` and `paid_social`).
- Controlling for `country_tier`, `platform`, and install week (HC3 robust SE), `paid_video` D30 LTV is **-$0.14** vs. `organic` (`95% CI: [-$0.45, +$0.16], p = 0.37`) and **+$0.11** vs. `paid_social` (`95% CI: [-$0.20, +$0.42], p = 0.49`).

## 4. Deliverable 4: 14-Day Churn Prediction
- **Definition:** Active in `[T-6, T]` (excluding Day-0 installs) with `0` sessions in `[T+1, T+14]` (justified empirically: 89.3% of returning players return within 14 days).
- **Temporal Split:** Train snapshot `2026-03-31` (`N = 29,921`, 19.9% churn); Out-of-time test snapshot `2026-04-15` (`N = 37,455`, 19.2% churn).
- **Performance & Policy:** Regularized logistic regression achieves **0.757 ROC-AUC** and **0.420 PR-AUC**. Target paid offers exclusively to at-risk payers at `p >= 0.50` (`~58%` precision) while using zero-cost push/soft-currency nudges for non-payers.
