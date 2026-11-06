"""
Run every query in sql/queries.sql against data/processed/retail.db and compare
results with reports/metrics.json (computed in Python). Prints PASS/FAIL per check
and exits 0 only if every check passes.

Tags understood in queries.sql:
  -- metric: <key>       scalar check
  -- metric_map: <key>   per-label check (rows of label, value)
  (no tag)               informational; printed, not checked

Run from anywhere:  python src/verify_sql.py
"""
import json, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'processed' / 'retail.db'
SQL = ROOT / 'sql' / 'queries.sql'
METRICS = ROOT / 'reports' / 'metrics.json'
TOL = 0.005  # both sides rounded to 2 dp

for p in (DB, METRICS, SQL):
    if not p.exists():
        sys.exit(f'Missing {p}. Run: python src/pipeline.py first.')

def parse_queries(text):
    blocks, cur = [], None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('-- name:'):
            if cur: blocks.append(cur)
            cur = {'name': s.split(':', 1)[1].strip(), 'metric': None, 'map': None, 'sql': []}
        elif s.startswith('-- metric_map:') and cur:
            cur['map'] = s.split(':', 1)[1].strip()
        elif s.startswith('-- metric:') and cur:
            cur['metric'] = s.split(':', 1)[1].strip()
        elif s.startswith('--') or not s:
            continue
        elif cur:
            cur['sql'].append(line)
    if cur: blocks.append(cur)
    return [dict(b, sql='\n'.join(b['sql']).strip().rstrip(';')) for b in blocks if b['sql']]

def close(a, b):
    return a is not None and b is not None and abs(float(a) - float(b)) <= TOL

metrics = json.loads(METRICS.read_text())
con = sqlite3.connect(DB)
checks = failures = 0
for q in parse_queries(SQL.read_text()):
    rows = con.execute(q['sql']).fetchall()
    if q['metric']:
        checks += 1
        sql_val, py_val = rows[0][0], metrics[q['metric']]
        ok = close(sql_val, py_val)
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {q['name']:<32} SQL={sql_val}  Python={py_val}")
    elif q['map']:
        py_map = metrics[q['map']]
        bad = []
        for label, val in rows:
            checks += 1
            ok = close(val, py_map.get(label))
            failures += not ok
            if not ok: bad.append((label, val, py_map.get(label)))
        extra = set(py_map) - {r[0] for r in rows}
        checks += 1
        if extra: failures += 1; bad.append(('missing-in-SQL', sorted(extra), None))
        status = 'PASS' if not bad else 'FAIL'
        print(f"{status}  {q['name']:<32} {len(rows)} labels checked against {q['map']}"
              + (f"  mismatches={bad}" if bad else ''))
    else:
        print(f"INFO  {q['name']}: {len(rows)} rows, first = {rows[0]}")
con.close()

print(f'\n{checks - failures}/{checks} checks passed')
sys.exit(1 if failures else 0)
