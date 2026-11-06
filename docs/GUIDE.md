# How to Build the Online Retail II Project

This guide explains the method behind each number in the resume bullets. Every figure is produced by `src/pipeline.py` and checked against `sql/queries.sql` by `src/verify_sql.py`. For run instructions, see `README.md`.

## 0. Setup
Put the source file at `data/raw/online_retail_II.xlsx`, then from the project root run:
```bash
pip install -r requirements.txt
python src/pipeline.py
python src/verify_sql.py
```

The pipeline writes:
- `data/processed/clean_transactions.csv`: cleaned product-sale transactions
- `data/processed/retail.db`: SQLite database with tables `raw_transactions` (deduplicated, all rows, with flags), `transactions` (clean), and `rfm`
- `reports/metrics.json`: every headline number, including per-segment values
- `reports/rfm_customers.csv`, `reports/rfm_segment_summary.csv`, `reports/cohort_retention_pct.csv`

Expect `30/30 checks passed` from the verifier.

## 1. Load and combine
The workbook has two sheets, one per fiscal year (`Year 2009-2010` and `Year 2010-2011`). Read both and stack them, keeping a `source_sheet` column so each row traces to its sheet. Total: 1,067,371 rows.

Two type rules apply on load:
- `Invoice` and `StockCode` are strings. Invoice numbers starting with "C" mark cancellations, and leading zeros in codes must survive.
- `Customer ID` is stored as `Int64`. Plain floats would show IDs as `13085.0`, and `Int64` keeps missing values as `<NA>` without changing the ID.

## 2. Remove exact duplicates
Drop rows identical on invoice, stock code, description, quantity, timestamp, price, customer, and country. This removes 34,335 rows and leaves 1,033,036. Duplicated lines would inflate revenue.

## 3. Quantify leakage before cleaning
Flag rows first and measure what will be removed. Report each category separately:
- **Cancellations:** invoices starting with "C" (19,104 rows). Cancelled revenue is 1,462,050.61, which is 7.14% of gross revenue.
- **Negative quantities without a "C" prefix:** stock adjustments (3,393 rows). Excluded from revenue.
- **Zero or negative prices:** free items and bad-debt adjustments (6,019 rows).
- **Non-product codes:** postage, bank charges, manual entries, and fees (5,973 rows).
- **Missing descriptions:** 4,275 rows.
- **Missing Customer ID:** 235,151 rows (22.8% of rows) but 15.15% of gross revenue. These rows cannot be attributed to a customer, so they are excluded from RFM and retention. Report them as their own finding.

## 4. Build the clean set
Keep rows that are not cancellations, have positive quantity and price, are product codes, and have a description. This leaves 1,003,219 rows (94.0% of raw). Revenue is `Quantity × Price`, rounded to two decimal places.

## 5. RFM segmentation

**Recency:** days from each customer's last purchase to the snapshot date (latest invoice date plus one day). The snapshot is fixed to the data, so results do not change with the run date.

**Frequency:** number of distinct invoices. **Monetary:** total revenue, rounded to two decimals.

**Scoring (tie-safe).** Each metric is converted to an average percentile rank, and the score is `ceil(percentile × 5)`, clipped to 1 to 5. Customers with identical values always get identical scores. The earlier method used `rank(method='first')`, which broke ties by row order, so customers with the same order count could land in different score bands depending on the sort. The tie-safe method changed 924 frequency scores and moved 379 customers into different segments.

Because many customers have one order (1,618 of 5,852), the frequency scores are not equal-sized bands: 1,618 customers score F = 1. This is expected and is why the scoring is not a pure quintile split.

**Segment rules.** Every R/F/M combination maps to exactly one segment, checked by an assertion in the pipeline:

| Segment | Rule |
|---|---|
| Champions | R ≥ 4 and F ≥ 4 |
| Loyal | R ≥ 3 and F ≥ 3 (not Champions) |
| New / Promising | R ≥ 4 and F ≤ 2 |
| Potential Loyalist | R = 3, F ≤ 2, M ≥ 3 |
| At Risk (high value) | R ≤ 2 and F ≥ 4 |
| At Risk | R ≤ 2 and F = 3 |
| Lapsed High-Spend | R ≤ 2, F ≤ 2, M ≥ 3 |
| Hibernating | R ≤ 2, F ≤ 2, M ≤ 2 |
| Needs Attention | R = 3, F ≤ 2, M ≤ 2 (the only remaining case) |

Lapsed High-Spend was added because the earlier rule set sent 277 lapsed, low-frequency, high-spend customers to the Needs Attention catch-all, which is the wrong group for them. Their revenue share is 2.00%.

**Top-N share.** Sort customers by monetary value, compute cumulative revenue, and read the share at 10% and 20% of identified customers.

## 6. Monthly cohort retention

**Cohort:** the month of each customer's first product purchase. **Cohort index:** months since the cohort month. **Retention:** distinct customers active at index N divided by cohort size.

**Censoring rules:**
1. **Left-censored cohort.** The data starts in December 2009, so the December 2009 cohort includes customers who were already active before the window opened. It is excluded from all retention figures. The December 2009 retention (about 42% at month 3) would otherwise overstate retention.
2. **Incomplete months.** December 2011 is partial (data ends December 9). A cohort counts toward month N only if its month N falls on or before November 2011. Each month has its own eligibility list, so month 6 uses 17 cohorts and month 1 uses 22.

**Two views of the same data:**
- **Eligibility-window view:** each month uses every cohort it can observe. Month 1 is 20.97%, month 3 is 21.09%, and month 6 is 18.45%.
- **Matched view:** the same 17 cohorts (Jan 2010 to May 2011) are used for all three months, so the comparison is like for like. Month 1 is 19.89%, month 3 is 20.62%, and month 6 is 18.45%.

The matched view is the basis for the recommendation, because it compares the same customers across months. Both views show the same pattern: retention is stable through month 3, then falls by month 6.

`reports/cohort_retention_pct.csv` has one row per cohort with flags: `left_censored`, `in_month1_eligible`, `in_month3_eligible`, `in_month6_eligible`, `in_matched_set`, and `status` (left-censored, incomplete for month 6, or complete for months 1 to 6).

**Weighting.** Report the weighted figure (total retained divided by total eligible cohort size), not the average of cohort percentages. Small cohorts would otherwise carry the same weight as large ones.

## 7. SQL layer
The pipeline loads `raw_transactions`, `transactions`, and `rfm` into SQLite. `sql/queries.sql` recomputes each headline metric from these tables. Each query is tagged with the metric it must match, and `src/verify_sql.py` runs them all:
- Cancellation and anonymous-revenue shares, from `raw_transactions`
- Top 10% and top 20% revenue shares, from `rfm`
- Customer count and revenue for each of the 9 segments, from `rfm`
- Month 1, 3, and 6 retention for both views

Two lessons from building it:
- Window functions with an explicit `ROWS BETWEEN UNBOUNDED PRECEDING` frame give the same cumulative sums as the Python version, with no tie-ordering ambiguity.
- Be careful with joins. When a per-cohort size is joined to per-customer activity rows, the denominator is multiplied by the number of activity rows. The first retention query returned 0.02% instead of 21.1% for this reason. Compute numerator and denominator in separate CTEs, then divide.

## 8. Write the recommendations
Each recommendation cites a measured number and a specific action. Example: "287 high-value customers average 337.8 days since last purchase, so send a personalized win-back offer and measure it against a holdout." Avoid claims the pipeline does not measure. The repeat-cancellation point is supported by customer-level counts of distinct C-prefixed cancellation invoices in `metrics.json`. Those counts describe cancellation records. The dataset does not link them to original invoices, so they cannot confirm cancelled orders. The pipeline also does not measure acquisition cost, margin, or campaign ROI, so recommendations about those must be framed as hypotheses to test.

## 9. Resume bullets
Each bullet covers one finding, with the action, scope, method, and result. Use only numbers from `metrics.json`. Bullets state raw and clean transaction counts separately, and report cancellation and anonymous revenue as separate findings.

## Common interview questions
- **Why exclude December 2009?** Left-censoring: those customers were already buyers before the data starts.
- **Why two retention views?** The eligibility-window view uses all available data. The matched view compares the same customers across months, which is required to say retention drops after month 3.
- **Why tie-safe scoring?** Row-order tie-breaking made scores depend on sort order. Average ranks give tied customers the same score.
- **What does a negative quantity without "C" mean?** Stock adjustments, not sales. They are excluded from revenue.
- **Why not delete the 235,151 rows with no Customer ID?** They hold 15.15% of gross revenue. Deleting them would understate the business. They are excluded only from customer-level analysis, which is a separate decision and should be stated as one.
- **How were RFM thresholds chosen?** Percentile-based scoring with hand-set segment rules. The rules are heuristic and should be tuned against business goals.
