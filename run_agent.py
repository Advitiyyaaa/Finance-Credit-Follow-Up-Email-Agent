"""
CLI Entry Point — run the Finance Credit Follow-Up Email Agent.

Usage:
    python run_agent.py --dry-run
    python run_agent.py --input data/invoices_may2025.csv --dry-run
"""

import argparse
import sys
import os

# Force unbuffered stdout for real-time output
sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONUNBUFFERED'] = '1'

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description="Finance Credit Follow-Up Email Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_agent.py --dry-run
  python run_agent.py --input data/custom_invoices.csv --dry-run
  python run_agent.py  # Uses defaults from .env
        """,
    )

    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to invoice CSV/Excel file (default: from .env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run in dry-run mode — no real emails sent (default: True)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Run in live mode — send real emails (requires SendGrid config)",
    )

    args = parser.parse_args()

    dry_run = not args.live  # --live overrides --dry-run

    from src.graph import run_agent

    summary = run_agent(
        input_path=args.input,
        dry_run=dry_run,
    )

    # Exit with error code if there were failures
    if summary.get("errors", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
