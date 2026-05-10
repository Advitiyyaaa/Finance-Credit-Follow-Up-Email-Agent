"""
Audit Log Viewer — CLI tool to inspect the audit trail.

Usage:
    python view_audit.py --last 50
    python view_audit.py --run-id <uuid>
    python view_audit.py --all
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.audit import get_recent_records, get_all_records, get_run_summary


def format_records(records: list[dict]) -> None:
    """Pretty-print audit records to console."""
    if not records:
        print("📭 No audit records found.")
        return

    try:
        from tabulate import tabulate

        # Select key columns for display
        display_cols = [
            "id", "run_id", "invoice_no", "client_name",
            "stage", "tone_used", "send_status", "sent_at",
        ]

        rows = []
        for r in records:
            row = {k: r.get(k, "N/A") for k in display_cols}
            # Truncate run_id for display
            if row["run_id"]:
                row["run_id"] = row["run_id"][:8] + "..."
            rows.append(row)

        print(tabulate(rows, headers="keys", tablefmt="grid"))

    except ImportError:
        # Fallback if tabulate not installed
        for r in records:
            print(
                f"  [{r.get('id', '?')}] {r.get('run_id', '?')[:8]}... | "
                f"{r.get('invoice_no', '?')} | {r.get('client_name', '?')} | "
                f"Stage {r.get('stage', '?')} | {r.get('send_status', '?')} | "
                f"{r.get('sent_at', '?')}"
            )

    print(f"\n📋 Total: {len(records)} record(s)")


def main():
    parser = argparse.ArgumentParser(
        description="View the audit log for the Credit Follow-Up Agent",
    )
    parser.add_argument("--last", type=int, default=50, help="Show last N records")
    parser.add_argument("--run-id", type=str, help="Show records for a specific run")
    parser.add_argument("--all", action="store_true", help="Show all records")

    args = parser.parse_args()

    print("\n📋 AUDIT LOG VIEWER\n" + "=" * 50 + "\n")

    if args.run_id:
        summary = get_run_summary(args.run_id)
        print(f"Run ID: {summary['run_id']}")
        print(f"Total: {summary['total_processed']}")
        print(f"By status: {summary['by_status']}")
        print(f"By stage: {summary['by_stage']}")
        print()

    if args.all:
        records = get_all_records()
    else:
        records = get_recent_records(limit=args.last)

    format_records(records)


if __name__ == "__main__":
    main()
