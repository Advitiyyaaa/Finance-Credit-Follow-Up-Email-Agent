"""
Send / Dry-Run Tool — dispatches emails via SMTP or logs them for review.
"""

from __future__ import annotations

import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import Dict

from .models import ClassifiedInvoice, EmailOutput
from .config import (
    DRY_RUN,
    SENDER_EMAIL,
    SENDER_NAME,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
)


def _mask_email(email: str) -> str:
    """Mask an email for console logging to protect PII."""
    if "@" not in email:
        return "***"
    local, domain = email.rsplit("@", 1)
    masked_local = local[0] + "****" if len(local) > 1 else "****"
    return f"{masked_local}@{domain}"


def _send_via_smtp(
    to_email: str,
    subject: str,
    body: str,
) -> Dict:
    """
    Send an email via SMTP (Gmail or any provider).

    Returns:
        Dict with keys: status, error_message, timestamp.
    """
    timestamp = datetime.utcnow().isoformat()

    if not SMTP_USER or not SMTP_PASSWORD:
        return {
            "status": "FAILED",
            "error_message": "SMTP credentials not configured in .env (SMTP_USER / SMTP_PASSWORD)",
            "timestamp": timestamp,
        }

    try:
        # Build the email
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Reply-To"] = SENDER_EMAIL

        # Plain text body
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Connect and send
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())

        return {
            "status": "SUCCESS",
            "error_message": None,
            "timestamp": timestamp,
        }

    except smtplib.SMTPAuthenticationError as e:
        return {
            "status": "FAILED",
            "error_message": f"SMTP authentication failed: {e}. "
                             "For Gmail, use an App Password: "
                             "https://myaccount.google.com/apppasswords",
            "timestamp": timestamp,
        }
    except smtplib.SMTPRecipientsRefused as e:
        return {
            "status": "FAILED",
            "error_message": f"Recipient refused: {e}",
            "timestamp": timestamp,
        }
    except Exception as e:
        return {
            "status": "FAILED",
            "error_message": f"SMTP error: {e}",
            "timestamp": timestamp,
        }


def send_or_dryrun(
    classified: ClassifiedInvoice,
    email: EmailOutput,
    run_id: str,
    dry_run: bool | None = None,
    output_dir: str = "data",
) -> Dict:
    """
    Send an email or log it in dry-run mode.

    Args:
        classified: The classified invoice.
        email: The generated email content.
        run_id: Unique ID for this agent run.
        dry_run: Override the global DRY_RUN setting.
        output_dir: Directory for dry-run JSON logs.

    Returns:
        Dict with keys: status, error_message, timestamp.
    """
    is_dry_run = dry_run if dry_run is not None else DRY_RUN
    inv = classified.invoice
    timestamp = datetime.utcnow().isoformat()

    if is_dry_run:
        # ── Dry-Run Mode: log to console + JSON file ──
        masked = _mask_email(inv.client_email)
        print(
            f"   [DRY-RUN] run_id={run_id[:6]} | {inv.invoice_no} | "
            f"{inv.client_name} | Stage {classified.stage} | "
            f"₹{inv.amount_due:,.0f} | {classified.days_overdue} days overdue → LOGGED"
        )

        # Write to JSON log
        log_entry = {
            "run_id": run_id,
            "timestamp": timestamp,
            "invoice_no": inv.invoice_no,
            "client_name": inv.client_name,
            "client_email_masked": masked,
            "amount_due": inv.amount_due,
            "days_overdue": classified.days_overdue,
            "stage": classified.stage,
            "tone": email.tone_used,
            "subject": email.subject,
            "body": email.body,
            "send_status": "DRY_RUN",
        }

        log_path = Path(output_dir) / "dry_run_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to existing log
        existing = []
        if log_path.exists():
            try:
                existing = json.loads(log_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception):
                existing = []

        existing.append(log_entry)
        log_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "status": "DRY_RUN",
            "error_message": None,
            "timestamp": timestamp,
        }
    else:
        # ── Live Send Mode via SMTP ──
        masked = _mask_email(inv.client_email)
        print(
            f"   [SEND] run_id={run_id[:6]} | {inv.invoice_no} | "
            f"{inv.client_name} → {masked}"
        )

        result = _send_via_smtp(
            to_email=inv.client_email,
            subject=email.subject,
            body=email.body,
        )

        if result["status"] == "SUCCESS":
            print(f"   [OK] Email sent to {masked}")
        else:
            print(f"   [FAIL] Send failed: {result['error_message']}")

        return result


def send_batch(
    email_queue: list[ClassifiedInvoice],
    generated_emails: dict,
    run_id: str,
    dry_run: bool | None = None,
) -> Dict[str, Dict]:
    """
    Send or dry-run all generated emails.

    Returns:
        Dict mapping invoice_no → send result.
    """
    results = {}

    for classified in email_queue:
        inv_no = classified.invoice.invoice_no
        email = generated_emails.get(inv_no)

        if email is None:
            results[inv_no] = {
                "status": "SKIPPED",
                "error_message": "Email generation failed",
                "timestamp": datetime.utcnow().isoformat(),
            }
            continue

        result = send_or_dryrun(
            classified=classified,
            email=email,
            run_id=run_id,
            dry_run=dry_run,
        )
        results[inv_no] = result

    return results
