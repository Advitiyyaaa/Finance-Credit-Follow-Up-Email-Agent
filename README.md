# Finance Credit Follow-Up Email Agent

> **Task 2** · AI Enablement Internship Project

An autonomous AI agent that monitors overdue invoices and sends progressively escalating payment reminder emails — keeping client relationships intact while reducing Days Sales Outstanding (DSO).

---

## Features

- **Automated Invoice Processing** — Reads pending invoices from CSV/Excel
- **4-Stage Tone Escalation** — From warm & friendly to stern & urgent
- **LLM-Powered Emails** — Google Gemini generates personalised, professional emails
- **Escalation Flagging** — 30+ day records flagged for manual finance/legal review
- **Immutable Audit Trail** — Every action logged to SQLite with SHA-256 body hashes
- **Dry-Run Mode** — Safe testing without sending real emails
- **Streamlit Dashboard** — Visual interface with real-time metrics

---

## Quick Start

### Prerequisites

- Python 3.11+
- A free Google Gemini API key ([Get one here](https://aistudio.google.com/apikey))

### Installation

```bash
git clone https://github.com/Advitiyyaaa/Finance-Credit-Follow-Up-Email-Agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Google API key
```

### Run the Agent (CLI)

```bash
# Dry-run mode (default — no real emails)
python run_agent.py --dry-run

# With custom input file
python run_agent.py --input data/sample_invoices.csv --dry-run

# View audit log
python view_audit.py --last 50
```

### Run the Dashboard (Streamlit)

```bash
streamlit run app.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                             │
│               (LangGraph StateGraph)                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────▼───────────────┐
         │       DATA INGESTION          │   CSV / Excel → pandas
         └───────────────┬───────────────┘
                         │
         ┌───────────────▼───────────────┐
         │     OVERDUE CLASSIFIER        │   days_overdue → stage
         └───────────────┬───────────────┘
                         │
         ┌───────────────▼───────────────┐
         │    EMAIL GENERATION           │   Gemini 2.0 Flash (LLM)
         └───────────────┬───────────────┘
                         │
         ┌───────────────▼───────────────┐
         │      SEND / DRY-RUN           │   Console log + JSON
         └───────────────┬───────────────┘
                         │
         ┌───────────────▼───────────────┐
         │        AUDIT LOGGER           │   SQLite audit trail
         └───────────────┬───────────────┘
                         │
         ┌───────────────▼───────────────┐
         │    ESCALATION FLAGGING        │   30+ days → manual review
         └───────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini 2.0 Flash (free tier) |
| Agent Framework | LangGraph 0.2.x |
| Data Ingestion | pandas, openpyxl |
| Output Validation | Pydantic v2 |
| Audit Log | SQLite |
| UI | Streamlit |
| Secrets | python-dotenv + .env |

---

## Tone Escalation Matrix

| Stage | Days Overdue | Tone | CTA |
|---|---|---|---|
| 1 | 1–7 | Warm & Friendly | Pay now link |
| 2 | 8–14 | Polite but Firm | Confirm payment date |
| 3 | 15–21 | Formal & Serious | Respond within 48 hrs |
| 4 | 22–30 | Stern & Urgent | Pay immediately |
| ESC | 30+ | 🚫 No auto-email | Assign to finance manager |

---

## Security Mitigations

| Risk | Mitigation |
|---|---|
| Prompt Injection | Input sanitisation (HTML stripping, length truncation), structured JSON output, Pydantic validation |
| Data Privacy / PII | Local processing, email masking in logs, SHA-256 body hashing in audit |
| API Key Exposure | .env + python-dotenv, .gitignore protection |
| Hallucination | Post-generation validation comparing LLM output against source data |
| Duplicate Sends | Audit log check before each send (same invoice_no + stage) |
| Rate Limiting | Max 100 invoices per run |

---

## Project Structure

```
├── agent.md                 # Architecture document
├── run_agent.py             # CLI entry point
├── view_audit.py            # Audit log viewer
├── app.py                   # Streamlit dashboard
├── requirements.txt
├── .env.example
├── src/
│   ├── config.py            # Configuration & constants
│   ├── models.py            # Pydantic data models
│   ├── ingest.py            # CSV/Excel ingestion
│   ├── classifier.py        # Overdue stage classifier
│   ├── email_generator.py   # LLM email generation
│   ├── sender.py            # Send / dry-run
│   ├── audit.py             # SQLite audit trail
│   ├── escalation.py        # Escalation flagging
│   └── graph.py             # LangGraph StateGraph
└── data/
    ├── sample_invoices.csv  # Sample data
    └── (audit_log.db)       # Created at runtime
```

---
