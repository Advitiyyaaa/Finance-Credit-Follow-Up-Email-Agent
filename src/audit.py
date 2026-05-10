"""
Audit Trail — SQLite-backed immutable log of every agent action.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from .models import AuditRecord
from .config import AUDIT_DB_PATH


# ── Schema ────────────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    invoice_no      TEXT NOT NULL,
    client_name     TEXT NOT NULL,
    amount_due      REAL NOT NULL,
    due_date        DATE NOT NULL,
    days_overdue    INTEGER NOT NULL,
    stage           INTEGER NOT NULL,
    tone_used       TEXT NOT NULL,
    subject         TEXT NOT NULL,
    body_hash       TEXT NOT NULL,
    send_status     TEXT NOT NULL,
    error_message   TEXT,
    sent_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_dry_run      BOOLEAN NOT NULL DEFAULT 1
);
"""


def _get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get a connection to the audit database, creating it if needed."""
    path = Path(db_path or AUDIT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()
    return conn


def check_duplicate(
    invoice_no: str,
    stage: int,
    db_path: str | None = None,
) -> bool:
    """
    Check if an email for this invoice + stage was already sent successfully.
    Prevents duplicate sends on agent re-runs.

    Returns:
        True if a SUCCESS record already exists (should skip).
    """
    conn = _get_connection(db_path)
    cursor = conn.execute(
        "SELECT COUNT(*) FROM audit_log "
        "WHERE invoice_no = ? AND stage = ? AND send_status = 'SUCCESS'",
        (invoice_no, stage),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def write_audit_record(record: AuditRecord, db_path: str | None = None) -> None:
    """Write a single audit record to the database."""
    conn = _get_connection(db_path)
    conn.execute(
        """
        INSERT INTO audit_log
            (run_id, invoice_no, client_name, amount_due, due_date,
             days_overdue, stage, tone_used, subject, body_hash,
             send_status, error_message, sent_at, is_dry_run)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.run_id,
            record.invoice_no,
            record.client_name,
            record.amount_due,
            record.due_date.isoformat(),
            record.days_overdue,
            record.stage,
            record.tone_used,
            record.subject,
            record.body_hash,
            record.send_status,
            record.error_message,
            record.sent_at.isoformat(),
            record.is_dry_run,
        ),
    )
    conn.commit()
    conn.close()


def write_audit_batch(records: List[AuditRecord], db_path: str | None = None) -> None:
    """Write multiple audit records in a single transaction."""
    conn = _get_connection(db_path)
    for record in records:
        conn.execute(
            """
            INSERT INTO audit_log
                (run_id, invoice_no, client_name, amount_due, due_date,
                 days_overdue, stage, tone_used, subject, body_hash,
                 send_status, error_message, sent_at, is_dry_run)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.invoice_no,
                record.client_name,
                record.amount_due,
                record.due_date.isoformat(),
                record.days_overdue,
                record.stage,
                record.tone_used,
                record.subject,
                record.body_hash,
                record.send_status,
                record.error_message,
                record.sent_at.isoformat(),
                record.is_dry_run,
            ),
        )
    conn.commit()
    conn.close()
    print(f"[LOG] {len(records)} audit record(s) written to database")


def get_recent_records(
    limit: int = 50,
    db_path: str | None = None,
) -> List[dict]:
    """Fetch the most recent audit records."""
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_all_records(db_path: str | None = None) -> List[dict]:
    """Fetch all audit records."""
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM audit_log ORDER BY id DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_run_summary(run_id: str, db_path: str | None = None) -> dict:
    """Get summary statistics for a specific run."""
    conn = _get_connection(db_path)
    conn.row_factory = sqlite3.Row

    total = conn.execute(
        "SELECT COUNT(*) as cnt FROM audit_log WHERE run_id = ?", (run_id,)
    ).fetchone()["cnt"]

    by_status = {}
    cursor = conn.execute(
        "SELECT send_status, COUNT(*) as cnt FROM audit_log "
        "WHERE run_id = ? GROUP BY send_status",
        (run_id,),
    )
    for row in cursor:
        by_status[row["send_status"]] = row["cnt"]

    by_stage = {}
    cursor = conn.execute(
        "SELECT stage, COUNT(*) as cnt FROM audit_log "
        "WHERE run_id = ? GROUP BY stage",
        (run_id,),
    )
    for row in cursor:
        by_stage[row["stage"]] = row["cnt"]

    conn.close()

    return {
        "run_id": run_id,
        "total_processed": total,
        "by_status": by_status,
        "by_stage": by_stage,
    }
