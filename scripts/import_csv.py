"""Load the six supplied CSVs into a fresh MySQL 8.0 database.

The MySQL client receives the password through its child-process environment;
neither SQL files nor command-line arguments contain credentials. All analytical
definitions live in ../sql, not in this loader.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys


PROJECT = Path(__file__).resolve().parents[1]
DB = "ecommerce_portfolio_v2"
TABLES = (
    ("users", "users.csv", 5000),
    ("products", "products.csv", 2000),
    ("orders", "orders.csv", 15000),
    ("user_behaviors", "user_behaviors.csv", 30000),
    ("user_features", "user_features.csv", 5000),
    ("product_features", "product_features.csv", 2000),
)
MYSQL_CANDIDATES = (
    Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"),
    Path(r"D:\Mysql\mysql-8.2.0-winx64\bin\mysql.exe"),
)


def mysql_binary() -> str:
    override = os.environ.get("MYSQL_BIN")
    if override:
        return override
    for candidate in MYSQL_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    executable = shutil.which("mysql")
    if executable:
        return executable
    raise SystemExit("mysql client not found; set MYSQL_BIN to its executable path")


def mysql(sql: str, password: str, *, database: bool = False) -> str:
    env = os.environ.copy()
    env["MYSQL_PWD"] = password
    cmd = [mysql_binary(), "--default-character-set=utf8mb4", "--batch", "--raw", "--silent", "-u", "root"]
    if database:
        cmd.extend(["--database", DB])
    proc = subprocess.run(cmd, input=sql, text=True, encoding="utf-8", errors="replace",
                          capture_output=True, env=env, check=False)
    if proc.returncode:
        raise RuntimeError(f"MySQL failed (exit {proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def sql_literal(value: str | None) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + (value.replace("\\", "\\\\").replace("'", "\\'")
                     .replace("\0", "\\0").replace("\n", "\\n")
                     .replace("\r", "\\r").replace("\x1a", "\\Z")) + "'"


def load_table(data_dir: Path, table: str, filename: str, expected: int, password: str) -> None:
    path = data_dir / filename
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"Missing header: {path}")
        columns = reader.fieldnames
        batches: list[str] = ["START TRANSACTION;\n"]
        values: list[str] = []
        count = 0
        for row in reader:
            if None in row:
                raise ValueError(f"Unexpected extra CSV fields at row {count + 2}: {path}")
            values.append("(" + ",".join(sql_literal(row[col]) for col in columns) + ")")
            count += 1
            if len(values) >= 250:
                batches.append(f"INSERT INTO `{table}` (" + ",".join(f"`{col}`" for col in columns)
                               + ") VALUES " + ",".join(values) + ";\n")
                values.clear()
        if values:
            batches.append(f"INSERT INTO `{table}` (" + ",".join(f"`{col}`" for col in columns)
                           + ") VALUES " + ",".join(values) + ";\n")
        batches.append("COMMIT;\n")
    if count != expected:
        raise ValueError(f"{filename}: expected {expected} rows, got {count}")
    mysql("".join(batches), password, database=True)
    actual = int(mysql(f"SELECT COUNT(*) FROM `{table}`;", password, database=True).strip())
    if actual != count:
        raise RuntimeError(f"{table}: loaded {actual} of {count} rows")
    print(f"{filename}: {actual} rows loaded", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path,
                        help="Directory containing the six original CSV files")
    parser.add_argument("--fresh", action="store_true",
                        help=f"Drop only {DB} before recreating it; never touches other databases")
    parser.add_argument("--analyze-only", action="store_true",
                        help="Rerun SQL views/checks after a code edit without importing CSVs again")
    args = parser.parse_args()
    if args.analyze_only and args.fresh:
        parser.error("--analyze-only and --fresh cannot be combined")
    if not args.analyze_only:
        if args.data_dir is None:
            parser.error("--data-dir is required unless --analyze-only is used")
        for _, filename, _ in TABLES:
            if not (args.data_dir / filename).is_file():
                parser.error(f"Missing {filename} in {args.data_dir}")
    password = os.environ.get("MYSQL_PASSWORD") or getpass.getpass("MySQL root password: ")
    if not args.analyze_only:
        if args.fresh:
            mysql(f"DROP DATABASE IF EXISTS `{DB}`;", password)
        schema = (PROJECT / "sql" / "00_schema.sql").read_text(encoding="utf-8")
        mysql(schema, password)
        for table, filename, expected in TABLES:
            load_table(args.data_dir, table, filename, expected, password)
    for filename in ("01_views.sql", "02_quality.sql", "03_analysis.sql",
                     "04_retention_experiment.sql", "05_dashboard.sql"):
        result = mysql((PROJECT / "sql" / filename).read_text(encoding="utf-8"), password)
        print(f"Executed {filename}", flush=True)
        if filename == "02_quality.sql":
            print(result, flush=True)
    failed = mysql("SELECT check_name,observed,expected FROM v_quality_checks "
                   "WHERE observed<>expected;", password, database=True).strip()
    if failed:
        raise RuntimeError("Quality checks failed:\n" + failed)
    print("All quality checks passed.")


if __name__ == "__main__":
    main()
