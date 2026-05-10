"""
Data Ingestion Tool — reads invoice data from CSV/Excel and validates schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from .models import Invoice
from .config import RATE_LIMIT_MAX_INVOICES


REQUIRED_COLUMNS = {
    "invoice_no",
    "client_name",
    "client_email",
    "amount_due",
    "due_date",
}


def load_invoices(file_path: str | Path) -> List[Invoice]:
    """
    Load invoice records from a CSV or Excel file.

    Args:
        file_path: Path to the data file (.csv or .xlsx).

    Returns:
        List of validated Invoice objects.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required columns are missing or data is invalid.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Invoice data file not found: {path}")

    # Read based on extension
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, engine="openpyxl")
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")

    # Normalise column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Validate required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}. "
            f"Found: {list(df.columns)}"
        )

    # Fill optional columns with defaults
    if "follow_up_count" not in df.columns:
        df["follow_up_count"] = 0
    if "payment_link" not in df.columns:
        df["payment_link"] = ""

    # Parse due_date
    df["due_date"] = pd.to_datetime(df["due_date"], dayfirst=False).dt.date

    # Rate limiting
    if len(df) > RATE_LIMIT_MAX_INVOICES:
        raise ValueError(
            f"Rate limit exceeded: {len(df)} invoices submitted, "
            f"max allowed is {RATE_LIMIT_MAX_INVOICES}."
        )

    # Convert to Invoice objects
    invoices: List[Invoice] = []
    errors: list[str] = []

    for idx, row in df.iterrows():
        try:
            inv = Invoice(
                invoice_no=str(row["invoice_no"]),
                client_name=str(row["client_name"]),
                client_email=str(row["client_email"]),
                amount_due=float(row["amount_due"]),
                due_date=row["due_date"],
                follow_up_count=int(row.get("follow_up_count", 0)),
                payment_link=str(row.get("payment_link", "")),
            )
            invoices.append(inv)
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    if errors:
        print(f"[WARN] {len(errors)} row(s) skipped due to validation errors:")
        for err in errors:
            print(f"   - {err}")

    if not invoices:
        raise ValueError("No valid invoices found in the file.")

    print(f"[OK] Loaded {len(invoices)} invoice(s) from {path.name}")
    return invoices
