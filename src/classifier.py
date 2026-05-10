"""
Overdue Classifier — computes days overdue and assigns escalation stage.
"""

from __future__ import annotations

from datetime import date
from typing import List, Tuple

from .models import Invoice, ClassifiedInvoice
from .config import TONE_MATRIX


def _stage_from_days(days_overdue: int) -> int:
    """Determine the escalation stage from days overdue."""
    if days_overdue <= 0:
        return 0  # Not overdue
    elif days_overdue <= 7:
        return 1
    elif days_overdue <= 14:
        return 2
    elif days_overdue <= 21:
        return 3
    elif days_overdue <= 30:
        return 4
    else:
        return 99  # Escalation flag


def _stage_from_follow_up_count(count: int) -> int:
    """
    Infer the minimum stage from the number of prior follow-ups.
    If a client has already received N follow-ups, they should be at least stage N+1
    (capped at 4).
    """
    if count <= 0:
        return 0
    return min(count, 4)


def classify_invoices(
    invoices: List[Invoice],
    reference_date: date | None = None,
) -> Tuple[List[ClassifiedInvoice], List[ClassifiedInvoice]]:
    """
    Classify invoices into email queue and escalation queue.

    Uses the stage override logic from agent.md:
        stage = max(days_overdue_stage, follow_up_count_stage)
    This ensures the tone never regresses if prior manual follow-ups
    already pushed the conversation forward.

    Args:
        invoices: List of validated Invoice objects.
        reference_date: The date to compute overdue against (defaults to today).

    Returns:
        Tuple of (email_queue, escalation_queue).
    """
    if reference_date is None:
        reference_date = date.today()

    email_queue: List[ClassifiedInvoice] = []
    escalation_queue: List[ClassifiedInvoice] = []

    for inv in invoices:
        days_overdue = (reference_date - inv.due_date).days

        if days_overdue <= 0:
            # Not yet overdue — skip
            print(f"   [SKIP] {inv.invoice_no} | {inv.client_name} | Not overdue (due in {-days_overdue} days)")
            continue

        # Compute stage with override logic
        stage_by_days = _stage_from_days(days_overdue)
        stage_by_count = _stage_from_follow_up_count(inv.follow_up_count)
        stage = max(stage_by_days, stage_by_count)

        # Cap at escalation if either signals it
        if stage_by_days == 99 or stage >= 5:
            stage = 99

        # Determine tone label
        if stage == 99:
            tone_label = "Escalation - No auto-email"
        elif stage in TONE_MATRIX:
            tone_label = TONE_MATRIX[stage]["label"]
        else:
            tone_label = "Unknown"

        classified = ClassifiedInvoice(
            invoice=inv,
            days_overdue=days_overdue,
            stage=stage,
            tone_label=tone_label,
        )

        if stage == 99:
            escalation_queue.append(classified)
            print(
                f"   [ALERT] {inv.invoice_no} | {inv.client_name} | "
                f"{days_overdue} days overdue -> ESCALATION FLAG"
            )
        else:
            email_queue.append(classified)
            print(
                f"   [EMAIL] {inv.invoice_no} | {inv.client_name} | "
                f"{days_overdue} days overdue -> Stage {stage} ({tone_label})"
            )

    print(
        f"\n[SUMMARY] Classification complete: "
        f"{len(email_queue)} for email, "
        f"{len(escalation_queue)} for escalation"
    )

    return email_queue, escalation_queue
