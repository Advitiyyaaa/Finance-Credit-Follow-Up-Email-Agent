# Finance Credit Follow-Up Email Agent

> **Task 2** · AI Enablement Internship Project  
> An autonomous agent that monitors overdue invoices and sends progressively escalating payment reminder emails — keeping client relationships intact while reducing Days Sales Outstanding (DSO).

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Agent Architecture](#2-agent-architecture)
3. [Agent Flow (Step-by-Step)](#3-agent-flow-step-by-step)
4. [Tone Escalation Matrix](#4-tone-escalation-matrix)
5. [Technical Stack & Decision Log](#5-technical-stack--decision-log)
6. [Prompt Design](#6-prompt-design)
7. [Security Risk Mitigations](#7-security-risk-mitigations)
8. [Audit Trail Schema](#8-audit-trail-schema)
9. [Setup Instructions](#9-setup-instructions)
10. [Sample Output](#10-sample-output)
11. [Deliverables Checklist](#11-deliverables-checklist)

---

## 1. Project Overview

### Business Problem

Finance teams spend hours every week manually chasing overdue payments. This process suffers from:

- **Inconsistent tone** — emails vary per team member, risking client friction or legal ambiguity.
- **Poor timing** — reminders are sent ad-hoc rather than on a structured schedule.
- **No audit trail** — hard to prove what was communicated and when.
- **Escalation gaps** — records that cross 30 days are often missed before legal referral.

### Solution

An AI agent that:

1. Reads all pending invoice records from a CSV/Excel/database source.
2. Computes the number of days each invoice is overdue.
3. Determines the correct escalation stage for each debtor.
4. Uses an LLM to generate a **personalised, stage-appropriate email** per invoice.
5. Sends the email via SMTP/SendGrid or logs it in dry-run mode.
6. Writes every action to an **immutable audit log**.
7. Flags any invoice beyond 30 days for **manual legal/finance review** instead of sending further emails.

---

## 2. Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                             │
│             (LangGraph StateGraph / LangChain AgentExecutor)    │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────▼───────────────┐
         │       DATA INGESTION TOOL     │
         │  CSV / Excel / SQLite reader  │
         │  (pandas + schema validation) │
         └───────────────┬───────────────┘
                         │  Structured invoice records
         ┌───────────────▼───────────────┐
         │     OVERDUE CLASSIFIER        │
         │  Computes days_overdue,       │
         │  assigns follow_up_stage,     │
         │  separates ESCALATION flags   │
         └───────────────┬───────────────┘
                         │  Staged invoice batches
         ┌───────────────▼───────────────┐
         │    EMAIL GENERATION TOOL      │
         │  System prompt + tone matrix  │
         │  Claude Sonnet 4 (LLM)        │
         │  Pydantic output validation   │
         └───────────────┬───────────────┘
                         │  Validated email objects
         ┌───────────────▼───────────────┐
         │      SEND / DRY-RUN TOOL      │
         │  SMTP / SendGrid API          │
         │  OR dry-run console log       │
         └───────────────┬───────────────┘
                         │  Send results
         ┌───────────────▼───────────────┐
         │        AUDIT LOGGER           │
         │  SQLite table / JSON log      │
         │  Timestamp, stage, status     │
         └───────────────┬───────────────┘
                         │
         ┌───────────────▼───────────────┐
         │    ESCALATION FLAGGING TOOL   │
         │  Marks 30+ day records for    │
         │  manual finance manager review│
         └───────────────────────────────┘
```

### Key Design Choices

| Decision | Choice | Rationale |
|---|---|---|
| Agent pattern | **Plan-and-Execute** (not ReAct) | Invoice processing is deterministic and sequential — no need for open-ended tool loop |
| State management | **LangGraph StateGraph** | Explicit node transitions make the escalation logic auditable and testable |
| LLM call granularity | One LLM call per invoice | Enables per-record personalisation; avoids context pollution across debtors |
| Output validation | **Pydantic models** | Guarantees all required fields (client name, invoice #, amount, etc.) are present before send |

---

## 3. Agent Flow (Step-by-Step)

```
Step 1 ── INGEST
         Load CSV/Excel → validate schema → parse into Invoice objects
                │
Step 2 ── CLASSIFY
         For each invoice:
           days_overdue = today − due_date
           stage = classify(days_overdue, follow_up_count)
           if stage == ESCALATION → route to flagging queue
           else → route to email queue
                │
Step 3 ── GENERATE EMAILS
         For each invoice in email queue:
           Build prompt with invoice fields + tone instructions
           Call LLM → parse Pydantic EmailOutput
           Validate all required fields populated
                │
Step 4 ── SEND / DRY-RUN
         if DRY_RUN=true  → print to console, write to log
         if DRY_RUN=false → send via SendGrid/SMTP
                │
Step 5 ── LOG
         Write to audit table:
           invoice_no, client, stage, tone, subject,
           body_hash, sent_at, send_status, error_msg
                │
Step 6 ── FLAG ESCALATIONS
         For each invoice in flagging queue:
           Update status = "ESCALATED"
           Notify finance manager (Slack webhook / email)
           Do NOT generate or send any automated email
                │
Step 7 ── REPORT SUMMARY
         Print / return:
           - Total processed
           - Emails sent per stage
           - Escalations flagged
           - Any failures
```

---

## 4. Tone Escalation Matrix

| Stage | Trigger (days overdue) | Tone | Key Message | CTA |
|---|---|---|---|---|
| **Stage 1** | 1 – 7 days | Warm & Friendly | Gentle reminder; assume oversight | Pay now link / bank details |
| **Stage 2** | 8 – 14 days | Polite but Firm | Payment still pending; request confirmation | Confirm payment date |
| **Stage 3** | 15 – 21 days | Formal & Serious | Escalating concern; mention impact on credit terms | Respond within 48 hrs |
| **Stage 4** | 22 – 30 days | Stern & Urgent | Final reminder before escalation to recovery | Pay immediately or call us |
| **Escalation Flag** | 30+ days | 🚫 No auto-email | Flag for legal/finance manager review | Assign to finance manager |

### Stage Override Logic

If `follow_up_count` in the data source is higher than what `days_overdue` alone implies (e.g. a client was emailed manually), the agent uses `max(days_overdue_stage, follow_up_count_stage)` to avoid regressing tone.

---

## 5. Technical Stack & Decision Log

### LLM

| Field | Value |
|---|---|
| **Model** | `claude-sonnet-4-20250514` (Claude Sonnet 4) |
| **Provider** | Anthropic |
| **Why this model** | 200K token context window (supports large invoice batches in context); excellent instruction-following for structured JSON output; cost-effective vs. Opus for a high-volume email generation task; native tool-calling support works cleanly with LangChain |
| **Alternatives considered** | GPT-4o — comparable quality but higher cost per token; Gemini 1.5 Flash — faster but weaker on nuanced tone calibration for formal/legal register |

### Agent Framework

| Field | Value |
|---|---|
| **Framework** | LangGraph `0.2.x` |
| **Architecture** | Plan-and-Execute StateGraph |
| **Why LangGraph** | Explicit state transitions prevent the agent from looping indefinitely on a failed email send; each node is independently testable; built-in checkpointing enables resuming interrupted runs without duplicate sends |
| **Alternatives considered** | LangChain AgentExecutor — simpler but less control over state; CrewAI — better for multi-agent collaboration, overkill here |

### Full Stack

| Layer | Technology |
|---|---|
| LLM | Claude Sonnet 4 via Anthropic Python SDK |
| Agent Framework | LangGraph 0.2.x |
| Data Ingestion | pandas, openpyxl |
| Output Validation | Pydantic v2 |
| Email Send | SendGrid Python SDK (`sendgrid`) |
| Dry-Run Mode | Console logger + JSON file |
| Scheduling | APScheduler (daily cron job) |
| Audit Log | SQLite (`audit_log` table) |
| Secrets Management | `python-dotenv` + `.env` file |
| UI (optional) | Streamlit dashboard |
| Observability (optional) | LangSmith tracing |

---

## 6. Prompt Design

### System Prompt (Email Generation Tool)

```
You are a professional finance communications assistant for [Company Name].
Your task is to write a payment reminder email for an overdue invoice.

RULES:
1. You MUST use ONLY the invoice data provided — never invent or assume any figures.
2. You MUST match the tone level exactly as instructed.
3. Output ONLY valid JSON matching the schema below. No preamble, no markdown fences.
4. Every field in the schema is required. If a field is missing from the input, return an error.

OUTPUT SCHEMA:
{
  "subject": "<email subject line>",
  "body": "<full email body, plain text>",
  "tone_used": "<stage_1|stage_2|stage_3|stage_4>",
  "fields_used": ["client_name", "invoice_no", "amount_due", "due_date", "days_overdue"]
}
```

### User Prompt Template (per invoice)

```
Write a Stage {stage} ({tone_label}) payment reminder email using ONLY this data:

- Client Name: {client_name}
- Invoice Number: {invoice_no}
- Amount Due: ₹{amount_due}
- Due Date: {due_date}
- Days Overdue: {days_overdue}
- Payment Link: {payment_link}
- Our Contact: {contact_email} / {contact_phone}

Tone instructions for Stage {stage}: {tone_instructions}
```

### Guardrails Applied

- **Structured JSON output** — Pydantic validation rejects any response missing required fields.
- **`fields_used` audit field** — forces the LLM to confirm it used real data, not hallucinated values.
- **No system prompt injection surface** — invoice data is inserted via f-string, not passed as free-form user input.
- **Temperature = 0.3** — low enough for consistent professional tone, high enough for natural variation across clients.

---

## 7. Security Risk Mitigations

| Risk | Description | Mitigation |
|---|---|---|
| **Prompt Injection** | Malicious content in invoice fields (e.g. a client name containing `"Ignore previous instructions..."`) manipulating LLM behaviour | All invoice fields are inserted into a structured template — not concatenated into a free-form prompt. Pydantic output parser rejects responses deviating from schema. Input fields are sanitised (strip HTML, truncate to max length) before prompt construction. |
| **Data Privacy / PII** | Invoice data contains personal names, emails, financial amounts | Processing runs locally. PII fields are masked in console logs (e.g. `client_email` → `r****@domain.com`). Audit table stores a SHA-256 hash of email body, not plaintext. No raw PII is written to external logging services. |
| **API Key Exposure** | Anthropic and SendGrid API keys leaked in source code | Keys stored in `.env` only. `.env` is in `.gitignore`. `.env.example` with placeholder values is committed instead. In production, keys are injected via environment variables from a secrets manager (AWS Secrets Manager / GCP Secret Manager). |
| **Hallucination Risk** | LLM generating wrong invoice amounts or client names | Pydantic model validates that `fields_used` includes all mandatory fields. A post-generation check compares LLM output against source data (amount, invoice number) and aborts send if mismatch detected. Human dry-run review mode available. |
| **Unauthorised Agent Trigger** | Anyone hitting the agent's API endpoint to trigger mass email sends | API endpoint protected by Bearer token authentication. Rate limiting (max 100 invoices per run) enforced. All trigger events logged with caller identity. |
| **Email Spoofing** | Emails appearing to come from an unverified sender domain | SPF, DKIM, and DMARC configured on sender domain. SendGrid verified sender identity required. `DRY_RUN=true` enforced in all non-production environments to prevent accidental real sends. |
| **Duplicate Sends** | Agent re-running and sending the same stage email twice | Audit log checked before each send: if a record with the same `invoice_no` + `stage` already has `send_status=SUCCESS`, the send is skipped. |

---

## 8. Audit Trail Schema

Every email action is written to an SQLite `audit_log` table:

```sql
CREATE TABLE audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,          -- UUID for this agent run
    invoice_no      TEXT NOT NULL,
    client_name     TEXT NOT NULL,
    amount_due      REAL NOT NULL,
    due_date        DATE NOT NULL,
    days_overdue    INTEGER NOT NULL,
    stage           INTEGER NOT NULL,       -- 1, 2, 3, 4, or 99 (escalation)
    tone_used       TEXT NOT NULL,
    subject         TEXT NOT NULL,
    body_hash       TEXT NOT NULL,          -- SHA-256 of email body
    send_status     TEXT NOT NULL,          -- SUCCESS | FAILED | DRY_RUN | SKIPPED
    error_message   TEXT,
    sent_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_dry_run      BOOLEAN NOT NULL DEFAULT 1
);
```

---

## 9. Setup Instructions

### Prerequisites

- Python 3.11+
- A SendGrid account (or use dry-run mode)
- An Anthropic API key

### Installation

```bash
git clone https://github.com/your-org/credit-followup-agent.git
cd credit-followup-agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables (`.env.example`)

```env
ANTHROPIC_API_KEY=your_anthropic_key_here
SENDGRID_API_KEY=your_sendgrid_key_here
SENDER_EMAIL=finance@yourcompany.com
DRY_RUN=true                     # Set to false for live sends
INVOICE_DATA_PATH=data/invoices.csv
AUDIT_DB_PATH=data/audit_log.db
ESCALATION_NOTIFY_EMAIL=manager@yourcompany.com
```

### Running the Agent

```bash
# Dry-run (no real emails sent)
python run_agent.py --dry-run

# Live run
DRY_RUN=false python run_agent.py

# Process a specific invoice file
python run_agent.py --input data/invoices_may2025.csv --dry-run

# View audit log
python view_audit.py --last 50
```

### Input CSV Format

```csv
invoice_no,client_name,client_email,amount_due,due_date,follow_up_count,payment_link
INV-2024-001,Rajesh Kapoor,rajesh@acmecorp.in,45000,2025-04-20,0,https://pay.co/inv001
INV-2024-002,Priya Sharma,priya@techsol.in,128000,2025-04-10,1,https://pay.co/inv002
```

---

## 10. Sample Output

### Stage 1 — Warm & Friendly

**Subject:** Quick Reminder – Invoice #INV-2024-001 | ₹45,000 Due

> Hi Rajesh,
>
> I hope you're doing well! This is a friendly reminder that Invoice #INV-2024-001 for ₹45,000 was due on 20 Apr 2025. If you've already processed this payment, please disregard this message.
>
> If not, you can complete the payment using the link below — it only takes a moment.
>
> 👉 Pay Now: https://pay.co/inv001
>
> Thank you for your continued partnership. Please don't hesitate to reach out if you have any questions.
>
> Warm regards,  
> Finance Team | Your Company

---

### Stage 4 — Stern & Urgent

**Subject:** FINAL NOTICE – Invoice #INV-2024-001 – Immediate Action Required

> Dear Mr. Kapoor,
>
> This is our final reminder. Invoice #INV-2024-001 for ₹45,000 is now 28 days overdue, despite three previous reminders.
>
> Failure to remit full payment within **24 hours** will result in this matter being escalated to our legal and recovery team, which may affect your credit terms and future business arrangements.
>
> Please act immediately: https://pay.co/inv001  
> Or contact us directly: finance@yourcompany.com | +91-XXXX-XXXXXX
>
> Regards,  
> Finance Recovery Team | Your Company

---

### Dry-Run Audit Log (console)

```
[DRY-RUN] run_id=a3f2c1 | INV-2024-001 | Rajesh Kapoor | Stage 1 | ₹45,000 | 5 days overdue → LOGGED
[DRY-RUN] run_id=a3f2c1 | INV-2024-002 | Priya Sharma  | Stage 2 | ₹1,28,000 | 12 days overdue → LOGGED
[ESCALATION] run_id=a3f2c1 | INV-2024-005 | Vikas Ltd    | 34 days overdue → FLAGGED FOR MANUAL REVIEW

Summary: 2 emails generated (dry-run) | 1 escalation flagged | 0 errors
```

---

## 11. Deliverables Checklist

- [x] GitHub repository with source code, `.env.example`, `requirements.txt`, `README.md`
- [x] `agent.md` — this document (architecture, prompts, security, setup)
- [x] Agent flow diagram (see Section 2)
- [x] Sample invoice CSV (`data/sample_invoices.csv`)
- [x] Sample audit log output (`data/sample_audit_log.json`)
- [x] 3–5 min screen recording of end-to-end dry-run
- [x] 8–10 slide presentation deck
- [x] Security mitigations section 

---
