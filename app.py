"""
Streamlit Dashboard — Finance Credit Follow-Up Email Agent
Run: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import json, os, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import INVOICE_DATA_PATH, COMPANY_NAME, TONE_MATRIX, GOOGLE_API_KEY
from src.audit import get_all_records, get_recent_records
from src.ingest import load_invoices
from src.classifier import classify_invoices

st.set_page_config(page_title=f"{COMPANY_NAME} — Credit Agent", page_icon="💰", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
* { font-family: 'Inter', sans-serif; }
.main-header { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 2rem; color: white; box-shadow: 0 8px 32px rgba(48,43,99,0.3); }
.main-header h1 { margin:0; font-size:2rem; font-weight:700; }
.main-header p { margin:0.5rem 0 0 0; opacity:0.8; }
.metric-card { background: linear-gradient(135deg, #1a1a2e, #16213e); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 1.5rem; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
.metric-value { font-size: 2.5rem; font-weight: 700; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.metric-label { font-size: 0.85rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 0.5rem; }
.stage-badge { display:inline-block; padding:0.3rem 0.8rem; border-radius:20px; font-size:0.75rem; font-weight:600; }
.stage-1{background:#065f46;color:#6ee7b7} .stage-2{background:#92400e;color:#fcd34d} .stage-3{background:#9a3412;color:#fdba74} .stage-4{background:#991b1b;color:#fca5a5} .stage-99{background:#581c87;color:#d8b4fe}
.email-preview { background:#1e1e2e; border:1px solid rgba(255,255,255,0.1); border-radius:12px; padding:1.5rem; margin:1rem 0; }
.email-preview .subject { font-weight:600; font-size:1.1rem; color:#e2e8f0; margin-bottom:1rem; padding-bottom:0.75rem; border-bottom:1px solid rgba(255,255,255,0.1); }
.email-preview .body { color:#cbd5e1; line-height:1.7; white-space:pre-wrap; }
</style>
""", unsafe_allow_html=True)

st.markdown(f'<div class="main-header"><h1>💰 Finance Credit Follow-Up Agent</h1><p>{COMPANY_NAME} · AI-Powered Payment Reminder System · Dry-Run Mode</p></div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")
    if GOOGLE_API_KEY:
        st.success("✅ Gemini API Key configured")
    else:
        st.error("❌ Gemini API Key missing")
    st.markdown("---")
    data_source = st.text_input("Invoice CSV path", value=INVOICE_DATA_PATH)
    st.markdown("---")
    st.markdown("### 🎯 Tone Matrix")
    for stage, cfg in TONE_MATRIX.items():
        d = cfg["days_range"]
        st.markdown(f'<span class="stage-badge stage-{stage}">Stage {stage}</span> {d[0]}–{d[1]}d — {cfg["label"]}', unsafe_allow_html=True)
    st.markdown('<span class="stage-badge stage-99">Escalation</span> 30+ days — 🚫 Manual Review', unsafe_allow_html=True)

tab_dash, tab_inv, tab_run, tab_audit, tab_email = st.tabs(["📊 Dashboard", "📋 Invoices", "🚀 Run Agent", "📝 Audit Log", "✉️ Emails"])

# Dashboard Tab
with tab_dash:
    try:
        records = get_all_records()
    except:
        records = []
    c1,c2,c3,c4 = st.columns(4)
    sent = sum(1 for r in records if r.get("send_status") in ("SUCCESS","DRY_RUN"))
    esc = sum(1 for r in records if r.get("stage")==99)
    fail = sum(1 for r in records if r.get("send_status")=="FAILED")
    runs = len(set(r.get("run_id","") for r in records))
    for col,val,lab in [(c1,sent,"Emails Logged"),(c2,esc,"Escalations"),(c3,fail,"Failed"),(c4,runs,"Runs")]:
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{val}</div><div class="metric-label">{lab}</div></div>', unsafe_allow_html=True)
    if records:
        st.markdown("### 📈 By Stage")
        sd = {}
        for r in records:
            s = r.get("stage",0); l = f"Stage {s}" if s!=99 else "Escalation"; sd[l]=sd.get(l,0)+1
        st.bar_chart(pd.DataFrame(list(sd.items()), columns=["Stage","Count"]).set_index("Stage"))
    else:
        st.info("📭 No data yet. Run the agent first.")

# Invoices Tab
with tab_inv:
    try:
        invoices = load_invoices(data_source)
        eq, escq = classify_invoices(invoices)
        rows = []
        for c in eq + escq:
            inv = c.invoice
            rows.append({"Invoice": inv.invoice_no, "Client": inv.client_name, "Amount": f"₹{inv.amount_due:,.0f}", "Due": str(inv.due_date), "Days": c.days_overdue, "Stage": c.stage if c.stage!=99 else "ESC", "Tone": c.tone_label})
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            c1,c2=st.columns(2); c1.metric("📧 Email Queue",len(eq)); c2.metric("🚨 Escalation",len(escq))
        else:
            st.success("✅ No overdue invoices!")
    except Exception as e:
        st.error(f"Error: {e}")

# Run Agent Tab
with tab_run:
    if not GOOGLE_API_KEY:
        st.error("❌ Add GOOGLE_API_KEY to .env first!\nGet one free at https://aistudio.google.com/apikey")
    else:
        st.info("💡 Dry-run mode — no real emails sent. All actions logged to audit trail.")
        if st.button("▶️ Run Agent", type="primary"):
            with st.spinner("🤖 Agent running..."):
                try:
                    from src.graph import run_agent
                    import io; from contextlib import redirect_stdout
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        summary = run_agent(input_path=data_source, dry_run=True)
                    st.success("✅ Complete!")
                    if summary:
                        c1,c2,c3 = st.columns(3)
                        c1.metric("Processed", summary.get("total_processed",0))
                        c2.metric("Emails", summary.get("emails_generated",0))
                        c3.metric("Escalations", summary.get("escalations_flagged",0))
                    with st.expander("📜 Console Output", expanded=True):
                        st.code(buf.getvalue(), language="text")
                except Exception as e:
                    st.error(f"❌ {e}")
                    import traceback; st.code(traceback.format_exc())

# Audit Tab
with tab_audit:
    limit = st.number_input("Records", min_value=5, max_value=500, value=50)
    try:
        recs = get_recent_records(limit=limit)
        if recs:
            df = pd.DataFrame(recs)
            cols = [c for c in ["id","run_id","invoice_no","client_name","amount_due","stage","tone_used","send_status","sent_at"] if c in df.columns]
            dfd = df[cols].copy()
            if "run_id" in dfd.columns:
                dfd["run_id"] = dfd["run_id"].str[:8]+"..."
            st.dataframe(dfd, use_container_width=True, hide_index=True)
            st.download_button("📥 Download CSV", df.to_csv(index=False), "audit.csv", "text/csv")
        else:
            st.info("📭 No records yet.")
    except:
        st.info("📭 No audit database. Run the agent first.")

# Email Preview Tab
with tab_email:
    log_path = Path("data/dry_run_log.json")
    if log_path.exists():
        try:
            emails = json.loads(log_path.read_text(encoding="utf-8"))
            if emails:
                opts = sorted(set(e.get("invoice_no","?") for e in emails))
                sel = st.selectbox("Invoice", ["All"]+opts)
                filt = emails if sel=="All" else [e for e in emails if e.get("invoice_no")==sel]
                for em in filt:
                    s = em.get("stage","?"); sc = f"stage-{s}" if s!=99 else "stage-99"
                    st.markdown(f'<div class="email-preview"><div style="display:flex;justify-content:space-between;margin-bottom:1rem"><span class="stage-badge {sc}">Stage {s}</span><span style="color:#6b7280;font-size:0.8rem">{em.get("invoice_no","?")} · ₹{em.get("amount_due",0):,.0f}</span></div><div class="subject">📧 {em.get("subject","")}</div><div class="body">{em.get("body","")}</div></div>', unsafe_allow_html=True)
            else:
                st.info("📭 Empty log.")
        except Exception as e:
            st.error(str(e))
    else:
        st.info("📭 No emails yet. Run the agent first.")

st.markdown("---")
st.markdown(f'<div style="text-align:center;color:#6b7280;font-size:0.8rem">🤖 {COMPANY_NAME} · Credit Follow-Up Agent · AI Enablement Internship</div>', unsafe_allow_html=True)
