"""
Configuration module — loads environment variables and defines constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ── LLM ──────────────────────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
LLM_MODEL = "gemini-2.5-flash"  # Free-tier Gemini model (confirmed working)
LLM_TEMPERATURE = 0.3  # Low for consistent professional tone

# ── Email ─────────────────────────────────────────────────────────────────────
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "finance@yourcompany.com")
SENDER_NAME = os.getenv("SENDER_NAME", "Finance Team")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# ── Agent ─────────────────────────────────────────────────────────────────────
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
INVOICE_DATA_PATH = os.getenv("INVOICE_DATA_PATH", "data/sample_invoices.csv")
AUDIT_DB_PATH = os.getenv("AUDIT_DB_PATH", "data/audit_log.db")

# ── Escalation ────────────────────────────────────────────────────────────────
ESCALATION_NOTIFY_EMAIL = os.getenv("ESCALATION_NOTIFY_EMAIL", "manager@yourcompany.com")

# ── Company Branding ──────────────────────────────────────────────────────────
COMPANY_NAME = os.getenv("COMPANY_NAME", "Acme Corp")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "finance@acmecorp.com")
CONTACT_PHONE = os.getenv("CONTACT_PHONE", "+91-9876-543210")

# ── Tone Escalation Matrix ────────────────────────────────────────────────────
TONE_MATRIX = {
    1: {
        "label": "Warm & Friendly",
        "days_range": (1, 7),
        "key_message": "Gentle reminder; assume oversight",
        "cta": "Pay now link / bank details",
        "instructions": (
            "Write in a warm, friendly, conversational tone. "
            "Assume the payment was simply overlooked. "
            "Express gratitude for their business. "
            "Include the payment link prominently. "
            "Keep it short and upbeat."
        ),
    },
    2: {
        "label": "Polite but Firm",
        "days_range": (8, 14),
        "key_message": "Payment still pending; request confirmation",
        "cta": "Confirm payment date",
        "instructions": (
            "Write in a polite but firm professional tone. "
            "Acknowledge that previous reminders may have been sent. "
            "Request the client confirm a specific payment date. "
            "Maintain professionalism while conveying mild urgency."
        ),
    },
    3: {
        "label": "Formal & Serious",
        "days_range": (15, 21),
        "key_message": "Escalating concern; mention impact on credit terms",
        "cta": "Respond within 48 hrs",
        "instructions": (
            "Write in a formal, serious business tone. "
            "Reference previous reminders. "
            "Mention that continued non-payment may impact credit terms or future business. "
            "Request a response within 48 hours. "
            "Use formal salutation (Dear Mr./Ms.)."
        ),
    },
    4: {
        "label": "Stern & Urgent",
        "days_range": (22, 30),
        "key_message": "Final reminder before escalation to recovery",
        "cta": "Pay immediately or call us",
        "instructions": (
            "Write in a stern, urgent tone. This is a FINAL NOTICE. "
            "State clearly that failure to pay within 24 hours will result in escalation "
            "to the legal and recovery team. "
            "Mention potential consequences (credit terms, legal action). "
            "Provide both payment link and direct contact number. "
            "Use uppercase for subject emphasis."
        ),
    },
}

# ── Security: Input sanitisation limits ───────────────────────────────────────
RATE_LIMIT_MAX_INVOICES = 100  # Max invoices per agent run
