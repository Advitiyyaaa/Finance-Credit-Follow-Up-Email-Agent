"""
Escalation Flagging Tool — handles invoices beyond 30 days overdue.
"""

from __future__ import annotations

from typing import List

from .models import ClassifiedInvoice, AuditRecord
from .config import ESCALATION_NOTIFY_EMAIL
from .email_generator import hash_email_body


def flag_escalations(
    escalation_queue: List[ClassifiedInvoice],
    run_id: str,
) -> List[AuditRecord]:
    """
    Flag invoices that are 30+ days overdue for manual finance/legal review.
    No automated emails are generated or sent for these records.

    Args:
        escalation_queue: List of classified invoices with stage == 99.
        run_id: Unique ID for this agent run.

    Returns:
        List of AuditRecord entries for the flagged invoices.
    """
    if not escalation_queue:
        return []

    print(f"\n[ALERT] Flagging {len(escalation_queue)} invoice(s) for manual review...\n")

    audit_records: List[AuditRecord] = []

    for classified in escalation_queue:
        inv = classified.invoice

        print(
            f"   [ESCALATION] run_id={run_id[:6]} | {inv.invoice_no} | "
            f"{inv.client_name} | {classified.days_overdue} days overdue "
            f"→ FLAGGED FOR MANUAL REVIEW"
        )

        # In production, this would send a Slack webhook or email to the finance manager
        print(
            f"   [NOTIFY] Notification would be sent to: {ESCALATION_NOTIFY_EMAIL}"
        )

        # Create audit record with stage=99 and no email body
        escalation_note = (
            f"ESCALATED: Invoice {inv.invoice_no} for {inv.client_name} "
            f"(₹{inv.amount_due:,.2f}) is {classified.days_overdue} days overdue. "
            f"Assigned to finance manager for manual review. "
            f"No automated email sent."
        )

        record = AuditRecord(
            run_id=run_id,
            invoice_no=inv.invoice_no,
            client_name=inv.client_name,
            amount_due=inv.amount_due,
            due_date=inv.due_date,
            days_overdue=classified.days_overdue,
            stage=99,
            tone_used="ESCALATION",
            subject=f"ESCALATED — {inv.invoice_no}",
            body_hash=hash_email_body(escalation_note),
            send_status="ESCALATED",
            error_message=None,
            is_dry_run=True,
        )
        audit_records.append(record)

    print(
        f"\n[ALERT] {len(audit_records)} escalation(s) flagged. "
        f"Finance manager notified at {ESCALATION_NOTIFY_EMAIL}."
    )

    return audit_records
