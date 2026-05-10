"""
LangGraph StateGraph — orchestrates the full agent pipeline.

Pipeline:
    INGEST → CLASSIFY → GENERATE → SEND → LOG → FLAG → REPORT
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, TypedDict, Any

from langgraph.graph import StateGraph, END

from .models import (
    Invoice,
    ClassifiedInvoice,
    EmailOutput,
    AuditRecord,
)
from .ingest import load_invoices
from .classifier import classify_invoices
from .email_generator import generate_emails_batch, hash_email_body
from .sender import send_batch
from .audit import write_audit_batch, check_duplicate
from .escalation import flag_escalations
from .config import DRY_RUN


# ── State type for LangGraph ──────────────────────────────────────────────────
class GraphState(TypedDict):
    run_id: str
    input_path: str
    dry_run: bool
    invoices: list
    email_queue: list
    escalation_queue: list
    generated_emails: dict
    send_results: dict
    audit_records: list
    escalation_records: list
    summary: dict
    errors: list


# ── Node Functions ────────────────────────────────────────────────────────────

def ingest_node(state: GraphState) -> dict:
    """Step 1: Load and validate invoice data."""
    print("\n" + "=" * 60)
    print(">> STEP 1 -- DATA INGESTION")
    print("=" * 60 + "\n")

    try:
        invoices = load_invoices(state["input_path"])
        return {"invoices": invoices, "errors": []}
    except Exception as e:
        error_msg = f"Ingestion failed: {e}"
        print(f"[FAIL] {error_msg}")
        return {"invoices": [], "errors": [error_msg]}


def classify_node(state: GraphState) -> dict:
    """Step 2: Classify invoices by overdue stage."""
    print("\n" + "=" * 60)
    print(">> STEP 2 -- OVERDUE CLASSIFICATION")
    print("=" * 60 + "\n")

    if not state.get("invoices"):
        return {"email_queue": [], "escalation_queue": []}

    email_queue, escalation_queue = classify_invoices(state["invoices"])
    return {
        "email_queue": email_queue,
        "escalation_queue": escalation_queue,
    }


def generate_node(state: GraphState) -> dict:
    """Step 3: Generate personalised emails via LLM."""
    print("\n" + "=" * 60)
    print(">> STEP 3 -- EMAIL GENERATION (Gemini)")
    print("=" * 60)

    email_queue = state.get("email_queue", [])
    if not email_queue:
        return {"generated_emails": {}}

    # Check for duplicates before generating
    filtered_queue = []
    for classified in email_queue:
        inv_no = classified.invoice.invoice_no
        stage = classified.stage
        if check_duplicate(inv_no, stage):
            print(
                f"   [SKIP] Skipping {inv_no} Stage {stage} -- "
                f"already sent successfully in a prior run"
            )
        else:
            filtered_queue.append(classified)

    generated = generate_emails_batch(filtered_queue)
    return {"generated_emails": generated, "email_queue": filtered_queue}


def send_node(state: GraphState) -> dict:
    """Step 4: Send emails or log in dry-run mode."""
    print("\n" + "=" * 60)
    print(">> STEP 4 -- SEND / DRY-RUN")
    print("=" * 60 + "\n")

    email_queue = state.get("email_queue", [])
    generated = state.get("generated_emails", {})

    if not email_queue or not generated:
        return {"send_results": {}}

    results = send_batch(
        email_queue=email_queue,
        generated_emails=generated,
        run_id=state["run_id"],
        dry_run=state.get("dry_run", True),
    )

    return {"send_results": results}


def log_node(state: GraphState) -> dict:
    """Step 5: Write audit records to SQLite."""
    print("\n" + "=" * 60)
    print(">> STEP 5 -- AUDIT LOGGING")
    print("=" * 60 + "\n")

    email_queue = state.get("email_queue", [])
    generated = state.get("generated_emails", {})
    send_results = state.get("send_results", {})
    run_id = state["run_id"]
    is_dry_run = state.get("dry_run", True)

    audit_records = []

    for classified in email_queue:
        inv = classified.invoice
        email = generated.get(inv.invoice_no)
        result = send_results.get(inv.invoice_no, {})

        if email is None:
            record = AuditRecord(
                run_id=run_id,
                invoice_no=inv.invoice_no,
                client_name=inv.client_name,
                amount_due=inv.amount_due,
                due_date=inv.due_date,
                days_overdue=classified.days_overdue,
                stage=classified.stage,
                tone_used="FAILED",
                subject="N/A",
                body_hash="N/A",
                send_status="FAILED",
                error_message="Email generation failed",
                is_dry_run=is_dry_run,
            )
        else:
            record = AuditRecord(
                run_id=run_id,
                invoice_no=inv.invoice_no,
                client_name=inv.client_name,
                amount_due=inv.amount_due,
                due_date=inv.due_date,
                days_overdue=classified.days_overdue,
                stage=classified.stage,
                tone_used=email.tone_used,
                subject=email.subject,
                body_hash=hash_email_body(email.body),
                send_status=result.get("status", "UNKNOWN"),
                error_message=result.get("error_message"),
                is_dry_run=is_dry_run,
            )

        audit_records.append(record)

    if audit_records:
        write_audit_batch(audit_records)

    return {"audit_records": audit_records}


def flag_node(state: GraphState) -> dict:
    """Step 6: Flag 30+ day invoices for manual review."""
    print("\n" + "=" * 60)
    print(">> STEP 6 -- ESCALATION FLAGGING")
    print("=" * 60)

    escalation_queue = state.get("escalation_queue", [])

    if not escalation_queue:
        print("\n   No escalations to flag.")
        return {"escalation_records": []}

    escalation_records = flag_escalations(
        escalation_queue=escalation_queue,
        run_id=state["run_id"],
    )

    # Write escalation audit records
    if escalation_records:
        write_audit_batch(escalation_records)

    return {"escalation_records": escalation_records}


def report_node(state: GraphState) -> dict:
    """Step 7: Print summary report."""
    print("\n" + "=" * 60)
    print(">> STEP 7 -- RUN SUMMARY")
    print("=" * 60 + "\n")

    audit_records = state.get("audit_records", [])
    escalation_records = state.get("escalation_records", [])
    errors = state.get("errors", [])

    total = len(audit_records) + len(escalation_records)
    emails_by_stage = {}
    for r in audit_records:
        stage = r.stage
        emails_by_stage[stage] = emails_by_stage.get(stage, 0) + 1

    statuses = {}
    for r in audit_records:
        statuses[r.send_status] = statuses.get(r.send_status, 0) + 1

    summary = {
        "run_id": state["run_id"],
        "total_processed": total,
        "emails_generated": len(audit_records),
        "escalations_flagged": len(escalation_records),
        "emails_by_stage": emails_by_stage,
        "send_statuses": statuses,
        "errors": len(errors),
    }

    mode = "DRY-RUN" if state.get("dry_run", True) else "LIVE"

    print(f"   Run ID:              {summary['run_id']}")
    print(f"   Mode:                {mode}")
    print(f"   Total processed:     {summary['total_processed']}")
    print(f"   Emails generated:    {summary['emails_generated']}")
    print(f"   Escalations flagged: {summary['escalations_flagged']}")
    print(f"   Errors:              {summary['errors']}")

    if emails_by_stage:
        print(f"\n   Emails by stage:")
        for stage, count in sorted(emails_by_stage.items()):
            print(f"     Stage {stage}: {count}")

    if statuses:
        print(f"\n   Send statuses:")
        for status, count in statuses.items():
            print(f"     {status}: {count}")

    if errors:
        print(f"\n   [WARN] Errors:")
        for err in errors:
            print(f"     - {err}")

    print("\n" + "=" * 60)
    print("[OK] Agent run complete.")
    print("=" * 60 + "\n")

    return {"summary": summary}


# ── Build the Graph ───────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construct the LangGraph StateGraph for the credit follow-up agent.

    Flow: INGEST → CLASSIFY → GENERATE → SEND → LOG → FLAG → REPORT
    """
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("send", send_node)
    workflow.add_node("log", log_node)
    workflow.add_node("flag", flag_node)
    workflow.add_node("report", report_node)

    # Define edges (sequential pipeline)
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "classify")
    workflow.add_edge("classify", "generate")
    workflow.add_edge("generate", "send")
    workflow.add_edge("send", "log")
    workflow.add_edge("log", "flag")
    workflow.add_edge("flag", "report")
    workflow.add_edge("report", END)

    return workflow


def run_agent(
    input_path: str | None = None,
    dry_run: bool = True,
) -> dict:
    """
    Execute the full agent pipeline.

    Args:
        input_path: Path to the invoice CSV/Excel file.
        dry_run: Whether to run in dry-run mode (no real emails sent).

    Returns:
        Final summary dict.
    """
    from .config import INVOICE_DATA_PATH

    workflow = build_graph()
    app = workflow.compile()

    initial_state: GraphState = {
        "run_id": str(uuid.uuid4()),
        "input_path": input_path or INVOICE_DATA_PATH,
        "dry_run": dry_run,
        "invoices": [],
        "email_queue": [],
        "escalation_queue": [],
        "generated_emails": {},
        "send_results": {},
        "audit_records": [],
        "escalation_records": [],
        "summary": {},
        "errors": [],
    }

    print("\n" + "=" * 60)
    print("  FINANCE CREDIT FOLLOW-UP EMAIL AGENT")
    print(f"  Mode: {'DRY-RUN' if dry_run else 'LIVE'}")
    print(f"  Input: {initial_state['input_path']}")
    print(f"  Run ID: {initial_state['run_id']}")
    print("=" * 60 + "\n")

    final_state = app.invoke(initial_state)

    return final_state.get("summary", {})
