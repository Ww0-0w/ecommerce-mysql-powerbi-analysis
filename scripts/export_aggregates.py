"""Export privacy-safe MySQL aggregates for the offline PBIX and report."""
from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
import os
from pathlib import Path

from import_csv import DB, PROJECT, TABLES, mysql


EXPORTS = {
    "overview": ("dashboard_overview", ""),
    "monthly": ("dashboard_monthly", "ORDER BY month_key"),
    "categories": ("dashboard_categories", "ORDER BY gmv DESC"),
    "rfm": ("dashboard_rfm", "ORDER BY gmv DESC"),
    "repeat": ("dashboard_repeat", "ORDER BY window_days"),
    "experiment": ("dashboard_experiment", "ORDER BY relative_lift_pct"),
    "quality": ("v_quality_checks", "ORDER BY check_name"),
}


def rows(query: str, password: str) -> list[list[str | None]]:
    result = mysql(query, password, database=True).strip()
    if not result:
        return []
    return [[None if value == "NULL" else value for value in line.split("\t")]
            for line in result.splitlines()]


def export_view(view: str, order: str, path: Path, password: str) -> list[dict[str, str | None]]:
    columns = [line[0] for line in rows(f"SHOW COLUMNS FROM `{view}`;", password)]
    data = rows(f"SELECT * FROM `{view}` {order};", password)
    records = [dict(zip(columns, item, strict=True)) for item in data]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)
    print(f"{path.name}: {len(records)} aggregate rows")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    password = os.environ.get("MYSQL_PASSWORD") or getpass.getpass("MySQL root password: ")
    out = PROJECT / "dashboard" / "data"
    out.mkdir(parents=True, exist_ok=True)
    exported = {}
    for name, (view, order) in EXPORTS.items():
        exported[name] = export_view(view, order, out / f"{name}.csv", password)

    extra_queries = {
        "median_order_payment": """WITH ranked AS (
          SELECT actual_payment,ROW_NUMBER() OVER (ORDER BY actual_payment,order_id) rn,
                 COUNT(*) OVER () n FROM v_valid_orders)
          SELECT AVG(actual_payment) FROM ranked
          WHERE rn IN (FLOOR((n+1)/2),FLOOR((n+2)/2));""",
        "one_time_buyers": "SELECT SUM(order_count=1) FROM v_user_purchase;",
        "repeat_buyer_gmv_pct": """SELECT 100*SUM(CASE WHEN order_count>1
          THEN total_spent ELSE 0 END)/SUM(total_spent) FROM v_user_purchase;""",
        "quantity_price_matches": """SELECT SUM(ABS(quantity*unit_price-total_amount)<=0.01)
          FROM orders;""",
        "asof_ts": "SELECT MAX(order_date) FROM orders;",
        "rfm_score_bounds": """SELECT r_score,MIN(recency_days),MAX(recency_days),
          f_score,MIN(order_count),MAX(order_count),m_score,MIN(total_spent),MAX(total_spent)
          FROM v_rfm_scored GROUP BY r_score,f_score,m_score
          ORDER BY r_score,f_score,m_score;""",
    }
    extras = {key: rows(query, password) for key, query in extra_queries.items()}
    (PROJECT / "report" / "analysis_results.json").write_text(
        json.dumps({"aggregates": exported, "extras": extras}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    manifest = []
    for _, filename, expected in TABLES:
        path = args.data_dir / filename
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        manifest.append({"filename": filename, "rows": expected,
                         "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    (PROJECT / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
