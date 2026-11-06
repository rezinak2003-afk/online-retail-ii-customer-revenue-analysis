"""
Online Retail II: end-to-end pipeline.
Input : data/raw/online_retail_II.xlsx
Output: data/processed/ (clean CSV, SQLite DB with raw/clean/RFM tables)
        reports/ (metrics.json, RFM and cohort tables)
Run   : python src/pipeline.py
"""
import json, sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'data' / 'raw' / 'online_retail_II.xlsx'
PROC = ROOT / 'data' / 'processed'; PROC.mkdir(parents=True, exist_ok=True)
REP = ROOT / 'reports'; REP.mkdir(parents=True, exist_ok=True)
if not SRC.exists():
    raise SystemExit(f'Missing input file: {SRC}\nPut online_retail_II.xlsx in data/raw/ first.')

MONEY = 2  # decimal places for monetary outputs

# 1. LOAD
x = pd.ExcelFile(SRC)
df = pd.concat([pd.read_excel(SRC, sheet_name=s).assign(source_sheet=s) for s in x.sheet_names],
               ignore_index=True)
df['Invoice'] = df['Invoice'].astype(str)
df['StockCode'] = df['StockCode'].astype(str)
df['Description'] = df['Description'].astype('string').str.strip()
# Customer IDs are whole numbers; Int64 keeps missing values as <NA> instead of 13085.0
df['Customer ID'] = df['Customer ID'].astype('Int64')
metrics = {'raw_rows': len(df)}

# 2. DEDUPLICATE
KEY = ['Invoice', 'StockCode', 'Description', 'Quantity', 'InvoiceDate', 'Price',
       'Customer ID', 'Country']
metrics['exact_duplicates_removed'] = int(df.duplicated(subset=KEY).sum())
df = df.drop_duplicates(subset=KEY).copy()
metrics['deduplicated_rows'] = len(df)

# 3. FLAGS
df['is_cancel'] = df['Invoice'].str.startswith('C')
df['has_customer'] = df['Customer ID'].notna()
df['revenue'] = (df['Quantity'] * df['Price']).round(MONEY)
NON_PRODUCT = r'(POST|D|M|BANK CHARGES|PADS|DOT|CRUK|C2|AMAZONFEE|S|B|ADJUST|TEST001|TEST002|DCGS.*|GIFT.*|m)'
df['is_nonproduct'] = df['StockCode'].str.fullmatch(NON_PRODUCT, case=False)
df['month'] = df['InvoiceDate'].dt.to_period('M').astype(str)

# 4. LEAKAGE
gross = df.loc[df['revenue'] > 0, 'revenue'].sum()
cancel_rev = -df.loc[df['is_cancel'], 'revenue'].sum()
anon_rev = df.loc[(df['revenue'] > 0) & ~df['has_customer'], 'revenue'].sum()
metrics.update({
    'gross_revenue': round(gross, MONEY),
    'cancelled_revenue': round(cancel_rev, MONEY),
    'cancelled_pct_of_gross': round(100 * cancel_rev / gross, 2),
    'cancel_rows': int(df['is_cancel'].sum()),
    'neg_qty_non_cancel_rows': int(((df['Quantity'] < 0) & ~df['is_cancel']).sum()),
    'zero_or_neg_price_rows': int((df['Price'] <= 0).sum()),
    'nonproduct_code_rows': int(df['is_nonproduct'].sum()),
    'missing_description_rows': int(df['Description'].isna().sum()),
    'missing_customer_rows': int((~df['has_customer']).sum()),
    'missing_customer_pct_rows': round(100 * (~df['has_customer']).mean(), 2),
    'missing_customer_revenue': round(anon_rev, MONEY),
    'missing_customer_pct_of_gross': round(100 * anon_rev / gross, 2),
})
# Repeat cancellers (customers with IDs only)
cancel_inv = (df[df['is_cancel'] & df['has_customer']].groupby('Customer ID')['Invoice'].nunique())
metrics['customers_with_cancellation'] = int(len(cancel_inv))
metrics['customers_with_2plus_cancellations'] = int((cancel_inv >= 2).sum())
metrics['pct_cancelling_customers_2plus'] = round(100 * (cancel_inv >= 2).mean(), 1)

# 5. CLEAN SET
clean = df[(~df['is_cancel']) & (df['Quantity'] > 0) & (df['Price'] > 0)
           & (~df['is_nonproduct']) & df['Description'].notna()].copy()
metrics['clean_rows'] = len(clean)
metrics['clean_rows_pct_of_raw'] = round(100 * len(clean) / metrics['raw_rows'], 2)
FLAG_COLS = ['is_cancel', 'is_nonproduct']
clean.drop(columns=FLAG_COLS).to_csv(PROC / 'clean_transactions.csv', index=False)

# 6. RFM (tie-safe scoring)
# Scores come from average percentile ranks, so customers with identical values
# always receive identical scores. Ties are not broken by row order.
def tie_safe_score(s):
    return np.ceil(s.rank(method='average', pct=True) * 5).clip(1, 5).astype(int)

c = clean[clean['has_customer']].copy()
c['Customer ID'] = c['Customer ID'].astype('int64')
snap = c['InvoiceDate'].max() + pd.Timedelta(days=1)
rfm = c.groupby('Customer ID').agg(
    recency=('InvoiceDate', lambda s: (snap - s.max()).days),
    frequency=('Invoice', 'nunique'),
    monetary=('revenue', 'sum')).reset_index()
rfm['monetary'] = rfm['monetary'].round(MONEY)
rfm['R'] = tie_safe_score(-rfm['recency'])   # fewer days since purchase = higher score
rfm['F'] = tie_safe_score(rfm['frequency'])
rfm['M'] = tie_safe_score(rfm['monetary'])

# Exhaustive segment rules: every R/F/M combination maps to exactly one segment.
def segment(r):
    if r.R >= 4 and r.F >= 4: return 'Champions'
    if r.R >= 3 and r.F >= 3: return 'Loyal'
    if r.R >= 4 and r.F <= 2: return 'New / Promising'
    if r.R == 3 and r.F <= 2 and r.M >= 3: return 'Potential Loyalist'
    if r.R <= 2 and r.F >= 4: return 'At Risk (high value)'
    if r.R <= 2 and r.F == 3: return 'At Risk'
    if r.R <= 2 and r.F <= 2 and r.M >= 3: return 'Lapsed High-Spend'
    if r.R <= 2 and r.F <= 2 and r.M <= 2: return 'Hibernating'
    return 'Needs Attention'           # only R == 3, F <= 2, M <= 2 reaches here
rfm['segment'] = rfm.apply(segment, axis=1)
assert rfm['segment'].notna().all()
rfm.to_csv(REP / 'rfm_customers.csv', index=False)

tot = rfm['monetary'].sum()
cum = rfm['monetary'].sort_values(ascending=False).cumsum() / tot
n = len(rfm)
metrics['customers'] = n
metrics['top10pct_revenue_share'] = round(100 * cum.iloc[int(round(n * 0.10)) - 1], 2)
metrics['top20pct_revenue_share'] = round(100 * cum.iloc[int(round(n * 0.20)) - 1], 2)

seg = rfm.groupby('segment').agg(
    customers=('Customer ID', 'count'),
    revenue=('monetary', 'sum'),
    avg_lifetime_revenue=('monetary', 'mean'),
    avg_orders=('frequency', 'mean'),
    avg_recency_days=('recency', 'mean')).sort_values('revenue', ascending=False)
seg['revenue_share_pct'] = (100 * seg['revenue'] / tot).round(2)
seg['revenue'] = seg['revenue'].round(MONEY)
seg['avg_lifetime_revenue'] = seg['avg_lifetime_revenue'].round(MONEY)
seg['avg_orders'] = seg['avg_orders'].round(2)
seg['avg_recency_days'] = seg['avg_recency_days'].round(1)
seg.to_csv(REP / 'rfm_segment_summary.csv')
metrics['segment_customers'] = {k: int(v) for k, v in seg['customers'].items()}
metrics['segment_revenue'] = {k: round(float(v), MONEY) for k, v in seg['revenue'].items()}
metrics['segment_revenue_share'] = {k: round(float(v), 2) for k, v in seg['revenue_share_pct'].items()}
metrics['lapsed_high_spend_customers'] = int((rfm['segment'] == 'Lapsed High-Spend').sum())

# 7. COHORT RETENTION
# Left-censored cohort: Dec 2009 (data starts that month). Excluded from all retention metrics.
# Per-month eligibility: cohort counts toward month N only if its month N is on or before
# Nov 2011, the last complete month (data ends Dec 9, 2011).
c['cohort'] = c.groupby('Customer ID')['InvoiceDate'].transform('min').dt.to_period('M')
c['cohort_index'] = (c['InvoiceDate'].dt.to_period('M') - c['cohort']).apply(lambda p: p.n)
size = c.groupby('cohort')['Customer ID'].nunique()
active = c.groupby(['cohort', 'cohort_index'])['Customer ID'].nunique().unstack()
LAST_FULL = pd.Period('2011-11', 'M')
FIRST_EXCL = pd.Period('2009-12', 'M')
MATCHED_MAX = pd.Period('2011-05', 'M')  # last cohort with 6 complete months observed

def eligible(m):
    return [p for p in size.index if p > FIRST_EXCL and p + m <= LAST_FULL]
matched = [p for p in size.index if FIRST_EXCL < p <= MATCHED_MAX]

ret = active.divide(size, axis=0) * 100
flags = pd.DataFrame({'cohort': [str(p) for p in size.index], 'cohort_size': size.values})
flags['left_censored'] = [p == FIRST_EXCL for p in size.index]
for m in (1, 3, 6):
    el = set(eligible(m))
    flags[f'in_month{m}_eligible'] = [p in el for p in size.index]
flags['in_matched_set'] = [p in set(matched) for p in size.index]
for m in range(0, 7):
    flags[f'm{m}_retention_pct'] = [round(ret.loc[p, m], 1) if (p in ret.index and m in ret.columns and not pd.isna(ret.loc[p, m])) else None for p in size.index]
flags['status'] = ['left-censored (excluded)' if p == FIRST_EXCL else
                   ('incomplete for month 6' if p + 6 > LAST_FULL and p > FIRST_EXCL else
                    'complete for months 1-6') for p in size.index]
flags.to_csv(REP / 'cohort_retention_pct.csv', index=False)

for m in (1, 3, 6):
    e = eligible(m)
    metrics[f'month{m}_eligible_cohorts'] = f'{e[0]} to {e[-1]} ({len(e)})'
    metrics[f'month{m}_retention_pct'] = round(100 * active.loc[e, m].sum() / size[e].sum(), 2)
    metrics[f'matched_month{m}_retention_pct'] = round(
        100 * active.loc[matched, m].sum() / size[matched].sum(), 2)
metrics['matched_cohorts'] = f'{matched[0]} to {matched[-1]} ({len(matched)})'

# 8. SQL LAYER (SQLite)
raw = df.copy()
for col in ['is_cancel', 'is_nonproduct', 'has_customer']:
    raw[col] = raw[col].astype(int)
raw_cols = ['Invoice', 'StockCode', 'Description', 'Quantity', 'InvoiceDate', 'Price',
            'Customer ID', 'Country', 'source_sheet', 'is_cancel', 'is_nonproduct',
            'has_customer', 'revenue', 'month']
con = sqlite3.connect(PROC / 'retail.db')
raw[raw_cols].to_sql('raw_transactions', con, if_exists='replace', index=False)
clean_out = clean.drop(columns=FLAG_COLS).copy()
clean_out['has_customer'] = clean_out['has_customer'].astype(int)
clean_out[[c_ for c_ in raw_cols if c_ not in FLAG_COLS]].to_sql(
    'transactions', con, if_exists='replace', index=False)
rfm.to_sql('rfm', con, if_exists='replace', index=False)
con.close()

with open(REP / 'metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2, default=str)
print(json.dumps(metrics, indent=2, default=str))
print(seg.to_string())
