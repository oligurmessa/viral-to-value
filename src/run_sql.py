"""
run_sql.py
==========
Builds a local DuckDB warehouse from data/raw using sql/schema.sql and runs
the analytical SQL scripts. PostgreSQL is the intended production engine;
DuckDB lets the same SQL run locally without a server.

    python src/run_sql.py                 # run all scripts, print head of each
    python src/run_sql.py --export        # also write results to data/processed/sql_*.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ["acquisition", "retention", "customer_ltv", "campaign_metrics"]


def build_db(db_path: Path | None = None, raw: Path = ROOT / "data/raw") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path) if db_path else ":memory:")
    con.execute((ROOT / "sql/schema.sql").read_text())
    for t in ["products", "campaigns", "customers", "orders", "sessions"]:
        con.execute(f"INSERT INTO {t} SELECT * FROM read_csv_auto('{raw / (t + '.csv')}', header=true)")
    return con


def run(con, name: str):
    sql = (ROOT / "sql" / f"{name}.sql").read_text()
    return con.execute(sql).df()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--db", default=None, help="optional path to persist the DuckDB file")
    a = ap.parse_args()
    con = build_db(Path(a.db) if a.db else None)
    for name in SCRIPTS:
        df = run(con, name)
        print(f"\n=== {name}.sql  ({len(df):,} rows) ===")
        print(df.head(8).to_string())
        if a.export:
            out = ROOT / "data/processed" / f"sql_{name}.csv"
            df.to_csv(out, index=False)
            print(f"-> {out}")
