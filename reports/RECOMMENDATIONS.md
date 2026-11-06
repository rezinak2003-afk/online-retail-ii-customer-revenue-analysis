# Online Retail II: Findings and Recommendations

All figures come from `reports/metrics.json` and are reproduced by `sql/queries.sql` (checked by `src/verify_sql.py`). Monetary values are in the dataset's native units; the source does not state a currency.

## Headline numbers
- **Transactions:** 1,067,371 raw rows. 34,335 exact duplicates were removed, leaving 1,033,036 rows. Removing cancellations, non-product codes, and invalid rows leaves 1,003,219 product-sale transactions (94.0% of raw rows).
- **Cancellations:** 7.14% of gross revenue (1,462,050.61 of 20,476,634.00). 2,572 customers have at least one C-prefixed cancellation invoice, and 1,414 of them (55.0%) have two or more distinct C-prefixed cancellation invoices. The dataset does not link cancellation records to their original invoices, so these counts describe cancellation records, not confirmed cancelled orders.
- **Anonymous revenue:** 15.15% of gross revenue has no Customer ID. These rows are 22.8% of all rows, so they cannot be attributed to a customer.
- **Concentration:** 5,852 identified customers. The top 10% drove 63.86% of revenue, and the top 20% drove 77.15%.
- **Retention (matched set of 17 cohorts, Jan 2010 to May 2011):** 19.89% of customers were active in month 1, 20.62% in month 3, and 18.45% in month 6. Retention rises slightly from month 1 to month 3, then falls by 2.17 points between month 3 and month 6. The decline happens in months 4 to 6, not earlier.

## Recommendations

1. **Re-engage customers in months 4 to 6.** Retention is stable through month 3 and drops by month 6. Trigger a re-engagement message on or around day 90 for customers who bought in their first three months but have not bought since. Measure it against a holdout group, because the matched-cohort decline is 2.17 points and a campaign should recover at least part of that.

2. **Protect the Champions.** 1,383 customers (23.6% of identified customers) generate 68.24% of revenue. They account for most of the revenue in this dataset, so retaining them is a priority. Give them early access, a loyalty tier, and account-level service. The dataset does not include acquisition costs or margins, so it cannot quantify the value of retention against acquisition.

3. **Win back high-value lapsed customers.** 287 customers in the At Risk (high value) segment average 8.6 orders and 3,318.29 in lifetime revenue, but their average last purchase was 337.8 days ago. Use a personalized win-back offer, not a generic discount, and measure reactivation against a holdout.

4. **Target Lapsed High-Spend customers separately.** 277 customers have low order frequency (1.65 orders on average) but high spend (1,235.14 average lifetime revenue), and their last purchase was 417 days ago on average. They do not fit the frequency-based At Risk segments, so they need their own offer. Together they account for 2.00% of revenue.

5. **Investigate repeat cancellation records.** 55.0% of customers with a C-prefixed cancellation invoice have two or more distinct cancellation invoices. Because the dataset does not link these records to original orders, first confirm what the records represent (for example, returns, corrections, or cancelled orders) before changing fulfillment. Cancellation records equal 7.14% of gross revenue.

6. **Capture Customer IDs at checkout.** 15.15% of gross revenue cannot be linked to a customer. Offer a reason to register, such as order tracking or a first-order discount. Each anonymous order is a sale that cannot be retargeted.

7. **Review paid promotion for Hibernating customers.** 1,354 customers (23.1% of identified customers) average 257.62 in lifetime revenue and 1.23 orders. The dataset has no campaign cost or margin data, so it cannot show whether paid reactivation would pay back. Test a small paid campaign against a holdout before committing budget, and use owned channels in the meantime.

## Caveats
- **Left-censored cohort.** The data starts in December 2009, so the December 2009 cohort (951 customers) was already active before the window opened. It is excluded from all retention figures. `reports/cohort_retention_pct.csv` flags it.
- **Incomplete months.** December 2011 is a partial month (data ends December 9). Cohorts whose month N falls after November 2011 are excluded for that month. `reports/cohort_retention_pct.csv` flags these cohorts.
- **Two retention views.** Each month's headline uses every cohort with that month observed (22, 20, and 17 cohorts for months 1, 3, and 6). The matched set uses the same 17 cohorts for all three months, which makes the month-to-month comparison fair. The eligibility-window figures are 20.97%, 21.09%, and 18.45%. Both views show the same decline after month 3.
- **RFM is heuristic.** Scores use average percentile ranks, so tied customers always get equal scores. Because many customers share the same order count (1,618 customers have one order), frequency scores are not equal-sized quintiles. Segment thresholds are judgment calls and should be tuned against business goals before production use.
- **Cancellation scope.** Cancellations are measured on invoices marked with a "C" prefix. Negative-quantity rows without that prefix (3,393 rows) are treated as stock adjustments and are excluded from the revenue figures.
