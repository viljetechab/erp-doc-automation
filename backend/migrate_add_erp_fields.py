"""Add missing ERP reference fields to orders table.

Columns added:
  - buyer_customer_number (Vårt kundnr → BuyerCodeEdi + CustomerInvoiceCode)
  - supplier_edi_code     (Leverantörsnummer → SupplierCodeEdi)
  - goods_marking         (Godsmärke → GoodsLabeling Row1)
  - delivery_is_buyer_address (CompanyAdressFlag: 1 if buyer==delivery, 0 otherwise)

Run this script once to update existing SQLite databases.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "orderflow_pro.db"


def migrate(db_path: Path = DB_PATH) -> None:
    """Add new columns to the orders table if they don't already exist."""
    if not db_path.exists():
        print(f"Database not found at {db_path} — skipping migration.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get existing column names
    cursor.execute("PRAGMA table_info(orders)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = [
        ("buyer_customer_number", "VARCHAR(100)"),
        ("supplier_edi_code", "VARCHAR(100)"),
        ("supplier_name", "VARCHAR(300)"),
        ("supplier_street", "VARCHAR(300)"),
        ("supplier_zip_city", "VARCHAR(200)"),
        ("supplier_country", "VARCHAR(100)"),
        ("goods_marking", "VARCHAR(500)"),
        ("delivery_is_buyer_address", "BOOLEAN"),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            sql = f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}"
            cursor.execute(sql)
            print(f"  [+] Added column: {col_name} ({col_type})")
        else:
            print(f"  [-] Column already exists: {col_name}")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH
    migrate(path)
