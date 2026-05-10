"""
Pydantic models for data validation throughout the agent pipeline.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re


class Invoice(BaseModel):
    """Raw invoice record from the data source."""

    invoice_no: str = Field(..., description="Unique invoice identifier")
    client_name: str = Field(..., description="Client / debtor name")
    client_email: str = Field(..., description="Client contact email")
    amount_due: float = Field(..., gt=0, description="Outstanding amount in INR")
    due_date: date = Field(..., description="Original payment due date")
    follow_up_count: int = Field(0, ge=0, description="Number of prior follow-ups")
    payment_link: str = Field("", description="URL for online payment")

    @field_validator("client_name", "client_email", "invoice_no", mode="before")
    @classmethod
    def sanitise_string(cls, v: str) -> str:
        """Strip HTML tags and limit length to prevent prompt injection."""
        if not isinstance(v, str):
            v = str(v)
        # Remove HTML tags
        v = re.sub(r"<[^>]+>", "", v)
        # Truncate
        return v[:200].strip()


class ClassifiedInvoice(BaseModel):
    """Invoice enriched with overdue classification."""

    invoice: Invoice
    days_overdue: int = Field(..., ge=0)
    stage: int = Field(..., description="1-4 for email stages, 99 for escalation")
    tone_label: str = Field(..., description="Human-readable tone description")


class EmailOutput(BaseModel):
    """Structured output from the LLM email generation."""

    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Full email body, plain text")
    tone_used: str = Field(..., description="stage_1 | stage_2 | stage_3 | stage_4")
    fields_used: List[str] = Field(
        ...,
        description="List of invoice fields used in the email",
    )


class AuditRecord(BaseModel):
    """Single audit log entry."""

    run_id: str
    invoice_no: str
    client_name: str
    amount_due: float
    due_date: date
    days_overdue: int
    stage: int
    tone_used: str
    subject: str
    body_hash: str
    send_status: str  # SUCCESS | FAILED | DRY_RUN | SKIPPED
    error_message: Optional[str] = None
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    is_dry_run: bool = True


