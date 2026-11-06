-- Each block: a name line, an optional metric tag, then SQL.
--   -- metric: <key>        scalar: first value must equal metrics.json[key]
--   -- metric_map: <key>    rows (label, value): each value must equal metrics.json[key][label]
--   (no tag)               informational only; printed, not checked

-- name: cancelled_pct_of_gross
-- metric: cancelled_pct_of_gross
SELECT ROUND(100.0 * (-SUM(CASE WHEN is_cancel = 1 THEN revenue ELSE 0 END))
       / SUM(CASE WHEN revenue > 0 THEN revenue ELSE 0 END), 2)
FROM raw_transactions;

-- name: missing_customer_pct_of_gross
-- metric: missing_customer_pct_of_gross
SELECT ROUND(100.0 * SUM(CASE WHEN "Customer ID" IS NULL AND revenue > 0 THEN revenue ELSE 0 END)
       / SUM(CASE WHEN revenue > 0 THEN revenue ELSE 0 END), 2)
FROM raw_transactions;

-- name: top10_revenue_share
-- metric: top10pct_revenue_share
WITH ranked AS (
  SELECT monetary,
         ROW_NUMBER() OVER (ORDER BY monetary DESC) AS rn,
         COUNT(*) OVER () AS n,
         SUM(monetary) OVER (ORDER BY monetary DESC
                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running
  FROM rfm)
SELECT ROUND(100.0 * MAX(running) / (SELECT SUM(monetary) FROM rfm), 2)
FROM ranked WHERE rn = CAST(ROUND(0.1 * n) AS INT);

-- name: top20_revenue_share
-- metric: top20pct_revenue_share
WITH ranked AS (
  SELECT monetary,
         ROW_NUMBER() OVER (ORDER BY monetary DESC) AS rn,
         COUNT(*) OVER () AS n,
         SUM(monetary) OVER (ORDER BY monetary DESC
                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running
  FROM rfm)
SELECT ROUND(100.0 * MAX(running) / (SELECT SUM(monetary) FROM rfm), 2)
FROM ranked WHERE rn = CAST(ROUND(0.2 * n) AS INT);

-- name: segment_customers
-- metric_map: segment_customers
SELECT segment, COUNT(*) FROM rfm GROUP BY segment;

-- name: segment_revenue
-- metric_map: segment_revenue
SELECT segment, ROUND(SUM(monetary), 2) FROM rfm GROUP BY segment;

-- name: segment_summary_info
SELECT segment, COUNT(*) AS customers, ROUND(SUM(monetary), 2) AS revenue,
       ROUND(100.0 * SUM(monetary) / (SELECT SUM(monetary) FROM rfm), 2) AS revenue_share_pct
FROM rfm GROUP BY segment ORDER BY revenue DESC;

-- name: month1_retention
-- metric: month1_retention_pct
WITH first_purchase AS (
  SELECT "Customer ID" AS cid, MIN(month) AS cohort
  FROM transactions WHERE "Customer ID" IS NOT NULL GROUP BY "Customer ID"),
eligible AS (
  SELECT cohort, COUNT(*) AS n FROM first_purchase
  WHERE cohort > '2009-12'
    AND (CAST(substr(cohort,1,4) AS INT)*12 + CAST(substr(cohort,6,2) AS INT)) + 1 <= 2011*12 + 11
    
  GROUP BY cohort),
active AS (
  SELECT f.cohort, COUNT(DISTINCT t."Customer ID") AS k
  FROM transactions t
  JOIN first_purchase f ON t."Customer ID" = f.cid
  JOIN eligible e ON e.cohort = f.cohort
  WHERE (CAST(substr(t.month,1,4) AS INT)*12 + CAST(substr(t.month,6,2) AS INT))
      - (CAST(substr(f.cohort,1,4) AS INT)*12 + CAST(substr(f.cohort,6,2) AS INT)) = 1
  GROUP BY f.cohort)
SELECT ROUND(100.0 * COALESCE((SELECT SUM(k) FROM active), 0) / (SELECT SUM(n) FROM eligible), 2);

-- name: month3_retention
-- metric: month3_retention_pct
WITH first_purchase AS (
  SELECT "Customer ID" AS cid, MIN(month) AS cohort
  FROM transactions WHERE "Customer ID" IS NOT NULL GROUP BY "Customer ID"),
eligible AS (
  SELECT cohort, COUNT(*) AS n FROM first_purchase
  WHERE cohort > '2009-12'
    AND (CAST(substr(cohort,1,4) AS INT)*12 + CAST(substr(cohort,6,2) AS INT)) + 3 <= 2011*12 + 11
    
  GROUP BY cohort),
active AS (
  SELECT f.cohort, COUNT(DISTINCT t."Customer ID") AS k
  FROM transactions t
  JOIN first_purchase f ON t."Customer ID" = f.cid
  JOIN eligible e ON e.cohort = f.cohort
  WHERE (CAST(substr(t.month,1,4) AS INT)*12 + CAST(substr(t.month,6,2) AS INT))
      - (CAST(substr(f.cohort,1,4) AS INT)*12 + CAST(substr(f.cohort,6,2) AS INT)) = 3
  GROUP BY f.cohort)
SELECT ROUND(100.0 * COALESCE((SELECT SUM(k) FROM active), 0) / (SELECT SUM(n) FROM eligible), 2);

-- name: month6_retention
-- metric: month6_retention_pct
WITH first_purchase AS (
  SELECT "Customer ID" AS cid, MIN(month) AS cohort
  FROM transactions WHERE "Customer ID" IS NOT NULL GROUP BY "Customer ID"),
eligible AS (
  SELECT cohort, COUNT(*) AS n FROM first_purchase
  WHERE cohort > '2009-12'
    AND (CAST(substr(cohort,1,4) AS INT)*12 + CAST(substr(cohort,6,2) AS INT)) + 6 <= 2011*12 + 11
    
  GROUP BY cohort),
active AS (
  SELECT f.cohort, COUNT(DISTINCT t."Customer ID") AS k
  FROM transactions t
  JOIN first_purchase f ON t."Customer ID" = f.cid
  JOIN eligible e ON e.cohort = f.cohort
  WHERE (CAST(substr(t.month,1,4) AS INT)*12 + CAST(substr(t.month,6,2) AS INT))
      - (CAST(substr(f.cohort,1,4) AS INT)*12 + CAST(substr(f.cohort,6,2) AS INT)) = 6
  GROUP BY f.cohort)
SELECT ROUND(100.0 * COALESCE((SELECT SUM(k) FROM active), 0) / (SELECT SUM(n) FROM eligible), 2);

-- name: matched_month1_retention
-- metric: matched_month1_retention_pct
WITH first_purchase AS (
  SELECT "Customer ID" AS cid, MIN(month) AS cohort
  FROM transactions WHERE "Customer ID" IS NOT NULL GROUP BY "Customer ID"),
eligible AS (
  SELECT cohort, COUNT(*) AS n FROM first_purchase
  WHERE cohort > '2009-12'
    AND (CAST(substr(cohort,1,4) AS INT)*12 + CAST(substr(cohort,6,2) AS INT)) + 1 <= 2011*12 + 11
    AND cohort <= '2011-05'
  GROUP BY cohort),
active AS (
  SELECT f.cohort, COUNT(DISTINCT t."Customer ID") AS k
  FROM transactions t
  JOIN first_purchase f ON t."Customer ID" = f.cid
  JOIN eligible e ON e.cohort = f.cohort
  WHERE (CAST(substr(t.month,1,4) AS INT)*12 + CAST(substr(t.month,6,2) AS INT))
      - (CAST(substr(f.cohort,1,4) AS INT)*12 + CAST(substr(f.cohort,6,2) AS INT)) = 1
  GROUP BY f.cohort)
SELECT ROUND(100.0 * COALESCE((SELECT SUM(k) FROM active), 0) / (SELECT SUM(n) FROM eligible), 2);

-- name: matched_month3_retention
-- metric: matched_month3_retention_pct
WITH first_purchase AS (
  SELECT "Customer ID" AS cid, MIN(month) AS cohort
  FROM transactions WHERE "Customer ID" IS NOT NULL GROUP BY "Customer ID"),
eligible AS (
  SELECT cohort, COUNT(*) AS n FROM first_purchase
  WHERE cohort > '2009-12'
    AND (CAST(substr(cohort,1,4) AS INT)*12 + CAST(substr(cohort,6,2) AS INT)) + 3 <= 2011*12 + 11
    AND cohort <= '2011-05'
  GROUP BY cohort),
active AS (
  SELECT f.cohort, COUNT(DISTINCT t."Customer ID") AS k
  FROM transactions t
  JOIN first_purchase f ON t."Customer ID" = f.cid
  JOIN eligible e ON e.cohort = f.cohort
  WHERE (CAST(substr(t.month,1,4) AS INT)*12 + CAST(substr(t.month,6,2) AS INT))
      - (CAST(substr(f.cohort,1,4) AS INT)*12 + CAST(substr(f.cohort,6,2) AS INT)) = 3
  GROUP BY f.cohort)
SELECT ROUND(100.0 * COALESCE((SELECT SUM(k) FROM active), 0) / (SELECT SUM(n) FROM eligible), 2);

-- name: matched_month6_retention
-- metric: matched_month6_retention_pct
WITH first_purchase AS (
  SELECT "Customer ID" AS cid, MIN(month) AS cohort
  FROM transactions WHERE "Customer ID" IS NOT NULL GROUP BY "Customer ID"),
eligible AS (
  SELECT cohort, COUNT(*) AS n FROM first_purchase
  WHERE cohort > '2009-12'
    AND (CAST(substr(cohort,1,4) AS INT)*12 + CAST(substr(cohort,6,2) AS INT)) + 6 <= 2011*12 + 11
    AND cohort <= '2011-05'
  GROUP BY cohort),
active AS (
  SELECT f.cohort, COUNT(DISTINCT t."Customer ID") AS k
  FROM transactions t
  JOIN first_purchase f ON t."Customer ID" = f.cid
  JOIN eligible e ON e.cohort = f.cohort
  WHERE (CAST(substr(t.month,1,4) AS INT)*12 + CAST(substr(t.month,6,2) AS INT))
      - (CAST(substr(f.cohort,1,4) AS INT)*12 + CAST(substr(f.cohort,6,2) AS INT)) = 6
  GROUP BY f.cohort)
SELECT ROUND(100.0 * COALESCE((SELECT SUM(k) FROM active), 0) / (SELECT SUM(n) FROM eligible), 2);
