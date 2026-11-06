# Online Retail II: Customer Revenue Analysis

Cleans 1.07M e-commerce transactions, quantifies revenue leakage, segments customers with RFM, and measures monthly cohort retention. Everything runs from one script and reproduces every number in the resume bullets.

## Project structure
```
online-retail-ii-project/
├── README.md                  <- you are here (execution steps)
├── requirements.txt           <- Python dependencies
├── .gitignore
├── data/
│   ├── raw/                   <- PUT THE SOURCE FILE HERE
│   │   └── .gitkeep           <- keeps this folder in the ZIP (see note below)
│   └── processed/             <- generated: clean CSV and SQLite DB
│       └── .gitkeep
├── src/
│   ├── pipeline.py            <- end-to-end pipeline (run first)
│   └── verify_sql.py          <- checks SQL results against Python (run second)
├── sql/
│   └── queries.sql            <- key metrics as SQL, each tagged with its Python metric
├── reports/
│   ├── metrics.json           <- every headline number
│   ├── rfm_customers.csv      <- per-customer R, F, M scores and segment
│   ├── rfm_segment_summary.csv
│   ├── cohort_retention_pct.csv
│   ├── RECOMMENDATIONS.md     <- findings and recommendations
│   └── RESUME_BULLETS.md      <- resume bullets with filled-in numbers
└── docs/
    └── GUIDE.md               <- methodology and interview prep
```

If `data/raw/` is missing after unzipping (some Windows archive tools drop empty folders), create it yourself in PowerShell with `New-Item -ItemType Directory -Force data\raw` and the same for `data\processed`. Then copy the workbook in.

## Requirements
- Python 3.9 or newer (check with `python3 --version`)
- About 2 GB free disk space
- Source file: `online_retail_II.xlsx` (two sheets: `Year 2009-2010`, `Year 2010-2011`)

## Step-by-step execution

### Step 1: Open a terminal in the project folder
- **macOS / Linux:** open Terminal, then `cd path/to/online-retail-ii-project`
- **Windows:** open PowerShell, then `cd path\to\online-retail-ii-project`

Confirm you are in the right place:
```bash
ls          # macOS / Linux
dir         # Windows
```
You should see `README.md`, `src`, `data`, and `reports`.

### Step 2: Place the source file
Copy `online_retail_II.xlsx` into `data/raw/` so the path is exactly:
```
data/raw/online_retail_II.xlsx
```
The name must match exactly, including case.

### Step 3: Create a virtual environment
This keeps the project's packages separate from the rest of your system.

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

When activation works, your prompt starts with `(.venv)`. If PowerShell blocks the activation script, run this once and try again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Step 4: Install dependencies
```bash
pip install -r requirements.txt
```
This installs `pandas` and `openpyxl`. It takes under a minute.

### Step 5: Run the pipeline
```bash
python src/pipeline.py
```
Expect this to take 1 to 3 minutes. It prints a JSON block of metrics and then the RFM segment table. The script exits with code 0 on success.

If you see `Missing input file`, return to Step 2.

### Step 6: Check the outputs
Confirm these files now exist:
```bash
ls data/processed     # clean_transactions.csv, retail.db
ls reports            # metrics.json, rfm_*.csv, cohort_retention_pct.csv
```

Open `reports/metrics.json` and confirm these values. If yours differ, stop and check the input file.

| Metric | Expected value |
|---|---|
| `raw_rows` | 1067371 |
| `exact_duplicates_removed` | 34335 |
| `deduplicated_rows` | 1033036 |
| `clean_rows` | 1003219 |
| `cancelled_pct_of_gross` | 7.14 |
| `missing_customer_pct_of_gross` | 15.15 |
| `customers` | 5852 |
| `top10pct_revenue_share` | 63.86 |
| `top20pct_revenue_share` | 77.15 |
| `segment_customers` → `Champions` | 1383 |
| `segment_customers` → `At Risk (high value)` | 287 |
| `lapsed_high_spend_customers` | 277 |
| `matched_month1_retention_pct` | 19.89 |
| `matched_month3_retention_pct` | 20.62 |
| `matched_month6_retention_pct` | 18.45 |

### Step 7: Validate the SQL layer
The pipeline saves the raw, clean, and RFM tables to `data/processed/retail.db`. The verifier runs every query in `sql/queries.sql` against that database, compares each result with the value Python computed, and prints PASS or FAIL for each check:

```bash
python src/verify_sql.py
```

Expected final line:
```
30/30 checks passed
```
The exit code is 0. Any FAIL line means SQL and Python disagree on that metric. Do not continue until all checks pass.

### Step 8: Read the findings
Open `reports/RECOMMENDATIONS.md` for the findings, and `docs/GUIDE.md` for how each number was produced.

### Step 9: Use the resume bullets
Copy from `reports/RESUME_BULLETS.md`. Use only numbers from `reports/metrics.json`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found | Try `python3`, or install Python from python.org |
| `Missing input file` | File must be at `data/raw/online_retail_II.xlsx` |
| `ModuleNotFoundError: pandas` | Activate the venv (Step 3), then rerun Step 4 |
| `MemoryError` | Close other applications. The pipeline needs about 2 GB of RAM |
| PowerShell blocks `Activate.ps1` | Run the `Set-ExecutionPolicy` command in Step 3 |
| Numbers differ from expected | Confirm the source file is the unmodified original |

## Re-running
Run `python src/pipeline.py` again at any time. It overwrites the outputs in `data/processed/` and `reports/`. Nothing in `data/raw/` is changed.

## Notes
- The source does not state a currency, so values are shown without a symbol.
- The December 2009 cohort and the partial December 2011 month are excluded from retention. `docs/GUIDE.md` explains why.
