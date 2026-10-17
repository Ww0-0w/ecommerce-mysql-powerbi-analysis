"""Independent stdlib checks of published MySQL aggregates against local CSVs.

This is a verification script, not the production analysis path. It reads raw
CSVs locally and writes no user-level output.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "dashboard" / "data"


def read(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    all_orders = read(args.data_dir / "orders.csv")
    valid = [r for r in all_orders if r["order_status"] not in
             {"已取消", "已退款", "待付款"}]
    overview = read(EXPORTS / "overview.csv")[0]
    assert len(all_orders) == int(overview["source_orders"]) == 15000
    assert len(valid) == int(overview["valid_orders"]) == 12765
    assert len(all_orders)-len(valid) == int(overview["excluded_orders"]) == 2235
    assert sum(Decimal(r["actual_payment"]) for r in valid) == Decimal(overview["gmv"])
    assert len({r["user_id"] for r in valid}) == int(overview["buyers"]) == 4605

    monthly = {r["month_key"]: r for r in read(EXPORTS / "monthly.csv")}
    assert set(monthly) == {"2025-10", "2025-11", "2025-12", "2026-01", "2026-02"}
    for month, published in monthly.items():
        subset = [r for r in valid if r["order_date"].startswith(month)]
        assert len(subset) == int(published["orders"])
        assert sum(Decimal(r["actual_payment"]) for r in subset) == Decimal(published["gmv"])

    asof = max(datetime.fromisoformat(r["order_date"]) for r in all_orders)
    by_user = defaultdict(list)
    for r in valid:
        by_user[r["user_id"]].append((datetime.fromisoformat(r["order_date"]),r["order_id"]))
    eligible = repeated = 0
    for orders in by_user.values():
        orders.sort()
        first_date, _ = orders[0]
        if asof-first_date < timedelta(days=30):
            continue
        eligible += 1
        repeated += any(date <= first_date + timedelta(days=30)
                        for date, _ in orders[1:])
    published_repeat = next(r for r in read(EXPORTS / "repeat.csv")
                            if r["window_days"] == "30")
    assert (eligible,repeated) == (int(published_repeat["eligible_buyers"]),
                                   int(published_repeat["repeat_buyers"])) == (4400,1536)

    rfm = read(EXPORTS / "rfm.csv")
    assert sum(int(r["buyers"]) for r in rfm) == 4605
    assert sum(Decimal(r["gmv"]) for r in rfm) == Decimal(overview["gmv"])
    for path in EXPORTS.glob("*.csv"):
        header = set(read(path)[0])
        assert not header.intersection({"user_id","order_id","product_id","credit_score",
                                        "account_balance","review_content"}), path
    quality = read(EXPORTS / "quality.csv")
    assert all(r["observed"] == r["expected"] for r in quality)
    print("PASS: source rows, GMV, monthly sums, 30-day cohort, RFM totals and public-field checks")


if __name__ == "__main__":
    main()
