"""
Email Generation Tool — uses Google Gemini to generate personalised payment reminders.
"""

from __future__ import annotations

import json
import re
import hashlib
import time
from typing import List

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from .models import ClassifiedInvoice, EmailOutput
from .config import (
    GOOGLE_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    TONE_MATRIX,
    COMPANY_NAME,
    CONTACT_EMAIL,
    CONTACT_PHONE,
)


# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a professional finance communications assistant for {COMPANY_NAME}.
Your task is to write a payment reminder email for an overdue invoice.

RULES:
1. You MUST use ONLY the invoice data provided — never invent or assume any figures.
2. You MUST match the tone level exactly as instructed.
3. Output ONLY valid JSON matching the schema below. No preamble, no markdown fences, no commentary.
4. Every field in the schema is required. If a field is missing from the input, return an error.
5. The email body must include: client name, invoice number, amount due, due date, and days overdue.
6. Do NOT use any markdown formatting in the email body. Plain text only.

OUTPUT SCHEMA:
{{
  "subject": "<email subject line>",
  "body": "<full email body, plain text>",
  "tone_used": "<stage_1|stage_2|stage_3|stage_4>",
  "fields_used": ["client_name", "invoice_no", "amount_due", "due_date", "days_overdue"]
}}"""


# ── User Prompt Template ──────────────────────────────────────────────────────
USER_PROMPT_TEMPLATE = """Write a Stage {stage} ({tone_label}) payment reminder email using ONLY this data:

- Client Name: {client_name}
- Invoice Number: {invoice_no}
- Amount Due: ₹{amount_due:,.2f}
- Due Date: {due_date}
- Days Overdue: {days_overdue}
- Payment Link: {payment_link}
- Our Contact: {contact_email} / {contact_phone}

Tone instructions for Stage {stage}: {tone_instructions}"""


# Retry configuration for free-tier rate limits
MAX_RETRIES = 3
RETRY_BASE_DELAY = 10  # seconds
INTER_CALL_DELAY = 5   # seconds between successive LLM calls
FALLBACK_MODEL = "gemini-1.5-flash-8b"


def _build_llm(model: str | None = None) -> ChatGoogleGenerativeAI:
    """Initialise the Gemini LLM."""
    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY is not set. "
            "Please add it to your .env file. "
            "Get a free key at https://aistudio.google.com/apikey"
        )

    return ChatGoogleGenerativeAI(
        model=model or LLM_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=LLM_TEMPERATURE,
        convert_system_message_to_human=True,
    )


def _parse_llm_response(raw_text: str) -> EmailOutput:
    """Parse LLM JSON response into EmailOutput, handling common formatting issues."""
    text = raw_text.strip()

    # Remove markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}\nRaw output:\n{text}")

    return EmailOutput(**data)


def _validate_email_against_source(
    email: EmailOutput, classified: ClassifiedInvoice
) -> List[str]:
    """
    Post-generation check: verify that the LLM used real data, not hallucinated values.
    Returns a list of warnings (empty if all checks pass).
    """
    warnings = []
    inv = classified.invoice

    # Check invoice number appears in the body
    if inv.invoice_no not in email.body:
        warnings.append(f"Invoice number {inv.invoice_no} not found in email body")

    # Check amount appears (with some tolerance for formatting)
    amount_str = f"{inv.amount_due:,.0f}"
    amount_plain = str(int(inv.amount_due))
    if amount_str not in email.body and amount_plain not in email.body:
        warnings.append(f"Amount {inv.amount_due} not found in email body")

    return warnings


def generate_email(
    classified: ClassifiedInvoice,
    llm: ChatGoogleGenerativeAI | None = None,
) -> EmailOutput:
    """
    Generate a personalised payment reminder email for a single classified invoice.

    Args:
        classified: The classified invoice with stage and tone info.
        llm: Optional pre-initialised LLM instance (for batch reuse).

    Returns:
        Validated EmailOutput object.
    """
    if llm is None:
        llm = _build_llm()

    inv = classified.invoice
    stage = classified.stage
    tone_config = TONE_MATRIX[stage]

    # Build the user prompt
    user_prompt = USER_PROMPT_TEMPLATE.format(
        stage=stage,
        tone_label=tone_config["label"],
        client_name=inv.client_name,
        invoice_no=inv.invoice_no,
        amount_due=inv.amount_due,
        due_date=inv.due_date.strftime("%d %b %Y"),
        days_overdue=classified.days_overdue,
        payment_link=inv.payment_link or "N/A",
        contact_email=CONTACT_EMAIL,
        contact_phone=CONTACT_PHONE,
        tone_instructions=tone_config["instructions"],
    )

    # Call LLM with retry logic for rate limits
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = llm.invoke(messages)
            email = _parse_llm_response(response.content)
            break
        except Exception as e:
            last_error = e
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait = RETRY_BASE_DELAY * (attempt + 1)
                print(f"   [WAIT] Rate limited, retrying in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
                # Try fallback model on last retry
                if attempt == MAX_RETRIES - 2:
                    print(f"   [SWITCH] Switching to fallback model: {FALLBACK_MODEL}")
                    llm = _build_llm(model=FALLBACK_MODEL)
            else:
                raise
    else:
        raise last_error

    # Post-generation validation
    warnings = _validate_email_against_source(email, classified)
    if warnings:
        print(f"   [WARN] Validation warnings for {inv.invoice_no}:")
        for w in warnings:
            print(f"      - {w}")

    return email


def generate_emails_batch(
    email_queue: List[ClassifiedInvoice],
) -> dict:
    """
    Generate emails for all invoices in the email queue.

    Returns:
        Dict mapping invoice_no → EmailOutput.
    """
    if not email_queue:
        print("[INFO] No invoices in the email queue.")
        return {}

    llm = _build_llm()
    results: dict = {}

    print(f"\n[EMAIL] Generating {len(email_queue)} email(s)...\n")

    for i, classified in enumerate(email_queue, 1):
        inv = classified.invoice
        print(
            f"   [{i}/{len(email_queue)}] {inv.invoice_no} | "
            f"{inv.client_name} | Stage {classified.stage}"
        )
        try:
            email = generate_email(classified, llm=llm)
            results[inv.invoice_no] = email
            print(f"   [OK] Subject: {email.subject}")
        except Exception as e:
            print(f"   [FAIL] Failed: {e}")
            results[inv.invoice_no] = None

        # Delay between calls to respect free-tier rate limits
        if i < len(email_queue):
            print(f"   [WAIT] Waiting {INTER_CALL_DELAY}s before next call...")
            time.sleep(INTER_CALL_DELAY)

    success = sum(1 for v in results.values() if v is not None)
    print(f"\n[DONE] Generated {success}/{len(email_queue)} email(s) successfully")

    return results


def hash_email_body(body: str) -> str:
    """SHA-256 hash of the email body for audit logging."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
