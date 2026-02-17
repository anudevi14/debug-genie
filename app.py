import streamlit as st
import json
import numpy as np
from src.config import Config
from src.clients.salesforce_client import SalesforceClient
from src.agents.ai_analyzer import AIAnalyzer
from src.engine.similarity_engine import SimilarityEngine
from src.engine.memory_manager import MemoryManager
from src.utils.log_parser import LogParser
from src.agents.investigation_graph import InvestigationGraph

# Page Configuration
st.set_page_config(
    page_title="DebugGenie - AI Production Copilot", 
    page_icon="🕵️",
    layout="wide"
)

# Custom CSS Injection
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("assets/style.css")

# Initialize Clients
@st.cache_resource
def get_clients():
    try:
        Config.validate()
        return SalesforceClient(), AIAnalyzer(), SimilarityEngine(), MemoryManager(), LogParser()
    except Exception as e:
        st.error(f"Configuration Error: {e}")
        return None, None, None, None, None

sf_client, ai_analyzer, similarity_engine, memory_manager, log_parser = get_clients()

# Initialization of Session State
if "analysis_result" not in st.session_state:
    st.session_state.update({
        "analysis_result": None,
        "case_num": None,
        "vision_data": None,
        "ticket_data": None,
        "text_for_embedding": None,
        "current_embedding": None,
        "similar_match": None,
        "feedback_submitted": False,
        "hist_context": None,
        "enhanced_result": None,
        "log_summary": None
    })

# Main Header
st.markdown('<div class="main-header">DebugGenie</div>', unsafe_allow_html=True)
st.markdown("#### Modern AI Production Copilot & RCA Engine")

if Config.MOCK_MODE:
    st.warning("⚠️ **Running in Mock Mode**: Data is hardcoded. Set `DEBUG_GENIE_MOCK_MODE=false` in `.env` to use real Salesforce data.")

# Sidebar for Semantic Memory Management
with st.sidebar:
    st.markdown("### 🧠 Semantic Intelligence")
    if memory_manager:
        stats = memory_manager.get_memory_stats()
        st.metric("Knowledge Base", f"{stats['entry_count']} Tickets")
        st.metric("Verified Patterns", f"{stats['verified_count']}")
        st.progress(stats['verified_count'] / max(stats['entry_count'], 1))
        st.caption(f"Avg Reliability Score: {stats['avg_reliability']:.2f}")
    
    st.markdown("---")
    if st.button("🔄 Sync & Backfill Knowledge"):
        if not sf_client:
            st.error("Salesforce client not initialized.")
        else:
            memory_manager.reload()
            with st.spinner("Backfilling semantic memory..."):
                historical_cases = sf_client.fetch_historical_cases(limit=100, filter_non_new=True)
                
            if historical_cases:
                progress_bar = st.progress(0)
                new_entries = []
                for i, case in enumerate(historical_cases):
                    case_num = case["CaseNumber"]
                    if not any(e["case_number"] == case_num for e in memory_manager.get_all_entries()):
                        text = sf_client.get_ticket_text_for_comparison(case)
                        embedding = ai_analyzer.get_embedding(text)
                        new_entries.append({
                            "case_number": case_num, "text": text, "embedding": embedding,
                            "root_cause": "N/A (Historical)", "resolution": "N/A (Historical)"
                        })
                    progress_bar.progress((i + 1) / len(historical_cases))
                
                if new_entries:
                    memory_manager.save_memory(new_entries)
                    st.success(f"Added {len(new_entries)} tickets!")
                    st.rerun()

# Search Section in a Card
with st.form("analysis_form"):
    col_input, col_btn = st.columns([4, 1])
    ticket_input = col_input.text_input("Enter Salesforce Ticket Number", placeholder="e.g. 12345678", label_visibility="collapsed")
    submit_button = col_btn.form_submit_button("Start Analysis")

if submit_button:
    if not ticket_input:
        st.warning("Please enter a ticket number.")
    elif not sf_client or not ai_analyzer:
        st.error("System configuration error.")
    else:
        try:
            st.session_state.update({
                "analysis_result": None, "case_num": ticket_input, "vision_data": None,
                "ticket_data": None, "text_for_embedding": None, "current_embedding": None,
                "similar_match": None, "feedback_submitted": False, "hist_context": None,
                "enhanced_result": None, "log_summary": None
            })

            with st.status("Performing Deep Investigation...", expanded=True) as status:
                graph = InvestigationGraph(sf_client, ai_analyzer, similarity_engine, memory_manager, log_parser)
                
                import asyncio
                
                initial_state = {
                    "ticket_id": ticket_input,
                    "log_data": None,
                    "status_updates": [],
                    "confidence_score": 0.0
                }
                
                final_state = {}
                
                async def run_analysis():
                    async for event in graph.workflow.astream(initial_state):
                        for node_name, output in event.items():
                            final_state.update(output)
                            if "status_updates" in output and output["status_updates"]:
                                st.write(output["status_updates"][-1])
                
                asyncio.run(run_analysis())
                
                # Update Session State from the accumulated final_state
                st.session_state.update({
                    "ticket_data": final_state.get("ticket_data"),
                    "vision_data": final_state.get("vision_data"),
                    "text_for_embedding": final_state.get("text_for_embedding"),
                    "current_embedding": final_state.get("current_embedding"),
                    "hist_context": final_state.get("similarity_context"),
                    "analysis_result": final_state.get("initial_rca"),
                    "similar_match": (final_state.get("similarity_context")["full_entry"], final_state.get("similarity_context")["score"]) 
                                     if final_state.get("similarity_context") else None
                })
                
                status.update(label="Investigation Complete!", state="complete", expanded=False)

            st.rerun()
                    
        except Exception as e:
            st.error(f"Error during analysis: {str(e)}")

# Helper: Custom SVG Gauge
def confidence_gauge(score):
    color = "#00F2FE" if score > 85 else ("#4FACFE" if score > 70 else "#F43F5E")
    gauge_html = f"""
    <div style="display: flex; justify-content: center; align-items: center; padding: 20px;">
        <svg width="200" height="200" viewBox="0 0 200 200">
            <circle cx="100" cy="100" r="90" fill="none" stroke="#1E293B" stroke-width="12" />
            <circle cx="100" cy="100" r="90" fill="none" stroke="{color}" stroke-width="12" 
                stroke-dasharray="{565 * score / 100} 565" stroke-linecap="round" 
                transform="rotate(-90 100 100)" style="transition: stroke-dasharray 1s ease-in-out;" />
            <text x="50%" y="50%" text-anchor="middle" dy=".3em" class="gauge-label">{score}%</text>
        </svg>
    </div>
    """
    st.markdown(gauge_html, unsafe_allow_html=True)

# DISPLAY RESULTS
if st.session_state.analysis_result:
    res = st.session_state.analysis_result
    
    # Dashboard Tabs
    tab_rca, tab_logs, tab_audit = st.tabs(["🎯 Stage 1: Initial RCA", "🔍 Stage 2: Log Deep-Dive", "📂 Technical Audit Trail"])

    with tab_rca:
        col_res, col_gauge = st.columns([3, 2])
        
        with col_res:
            st.markdown(f"### Root Cause Analysis for #{st.session_state.case_num}")
            
            badge_html = ""
            if st.session_state.vision_data:
                badge_html += '<span style="background:#00F2FE; color:#0e1117; padding:4px 10px; border-radius:100px; font-weight:800; font-size:12px; margin-right:8px;">VISION ACTIVE</span>'
            if st.session_state.similar_match:
                badge_html += f'<span style="background:#4FACFE; color:white; padding:4px 10px; border-radius:100px; font-weight:800; font-size:12px;">PATTERN MATCH: {res.get("similarityScore", 0.0)}</span>'
            st.markdown(badge_html, unsafe_allow_html=True)
            
            st.markdown("#### impacted Service")
            st.info(f"📍 **{res.get('impactedService', 'Unknown')}**")

            st.markdown("#### root Cause Hypothesis")
            root_cause = res.get("probableRootCause") or "N/A"
            st.markdown(f'<div class="analysis-box">{root_cause}</div>', unsafe_allow_html=True)

            st.markdown("#### recommended Mitigation")
            raw_steps = res.get("recommendedSteps") or ""
            steps = raw_steps if isinstance(raw_steps, list) else raw_steps.split(". ")
            
            # Group numbered markers with their steps
            processed_steps = []
            temp_step = ""
            for s in steps:
                s = s.strip()
                if not s: continue
                if s.isdigit() and len(s) <= 2:
                    temp_step = s + ". "
                else:
                    processed_steps.append(temp_step + s)
                    temp_step = ""
            
            for step in processed_steps:
                st.markdown(f'<div class="action-card">🛠️ {step.strip().strip(".")}</div>', unsafe_allow_html=True)

            # Restored Missing Details
            if res.get("splunkQuerySuggestion") and res.get("splunkQuerySuggestion") != "N/A":
                st.markdown("#### suggested Splunk Query")
                st.code(res.get("splunkQuerySuggestion"), language="spl")

            if res.get("isRepeatedIssue"):
                st.markdown("#### 🔄 Repeated Issue Detected")
                st.warning(f"Similar Case: **{res.get('similarTicketReference')}**")
        
        with col_gauge:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div style="text-align: center;">', unsafe_allow_html=True)
            st.markdown("### Confidence")
            confidence_gauge(res.get("confidence_score", 0))
            st.markdown(f'<p style="color:var(--text-secondary);">{res.get("confidence_reasoning")}</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Feedback & Expert Validation
            st.markdown("---")
            st.markdown("##### Expert Validation")
            
            if st.session_state.feedback_submitted:
                st.success("✅ Feedback saved to Knowledge Base!")
                if st.button("Provide New Feedback"):
                    st.session_state.feedback_submitted = False
                    st.rerun()
            else:
                f1, f2, f3 = st.columns([1, 1, 1])
                
                # Correction Mode Toggle
                if "edit_mode" not in st.session_state:
                    st.session_state.edit_mode = False
                
                if f1.button("✅ Accurate", use_container_width=True):
                    fb = {"probableRootCause": res.get("probableRootCause"), "recommendedSteps": res.get("recommendedSteps")}
                    memory_manager.submit_feedback(st.session_state.case_num, "correct", fb, text=st.session_state.text_for_embedding, embedding=st.session_state.current_embedding)
                    st.session_state.feedback_submitted = True
                    st.rerun()
                
                if f2.button("❌ Inaccurate", use_container_width=True):
                    fb = {"probableRootCause": res.get("probableRootCause"), "recommendedSteps": res.get("recommendedSteps")}
                    memory_manager.submit_feedback(st.session_state.case_num, "incorrect", fb, text=st.session_state.text_for_embedding, embedding=st.session_state.current_embedding)
                    st.session_state.feedback_submitted = True
                    st.rerun()

                if f3.button("📝 Edit", use_container_width=True):
                    st.session_state.edit_mode = not st.session_state.edit_mode
                
                if st.session_state.edit_mode:
                    with st.form("edit_rca_form"):
                        st.markdown("#### analyst Correction")
                        new_rc = st.text_area("Correct Root Cause", value=res.get("probableRootCause"))
                        new_steps = st.text_area("Correct Resolution Steps", value=res.get("recommendedSteps") if isinstance(res.get("recommendedSteps"), str) else ". ".join(res.get("recommendedSteps")))
                        
                        if st.form_submit_button("Save Corrections"):
                            fb = {"probableRootCause": new_rc, "recommendedSteps": new_steps}
                            memory_manager.submit_feedback(st.session_state.case_num, "correct", fb, text=st.session_state.text_for_embedding, embedding=st.session_state.current_embedding)
                            st.session_state.feedback_submitted = True
                            st.session_state.edit_mode = False
                            st.rerun()

    with tab_logs:
        st.markdown("### Log-Aware Investigation Engine")
        st.write("Upload Splunk logs to dynamically recalibrate the RCA and confidence scores.")
        
        l_col1, l_col2 = st.columns([2, 1])
        with l_col1:
            log_input = st.text_area(
                "Paste Raw Logs", 
                height=200, 
                placeholder="Starting Splunk log dump here...",
                key=f"log_input_{st.session_state.case_num}"
            )
        with l_col2:
            uploaded_log = st.file_uploader(
                "Or Upload .log file", 
                type=["log", "txt"],
                key=f"log_file_{st.session_state.case_num}"
            )
        
        log_txt = log_input or (uploaded_log.read().decode("utf-8") if uploaded_log else "")
        if st.button("🚀 Re-Analyze with Logs", use_container_width=True):
            if not log_txt:
                st.warning("Please provide logs for re-analysis.")
            else:
                with st.status("Correlating log signals with ticket context...", expanded=True) as status:
                    graph = InvestigationGraph(sf_client, ai_analyzer, similarity_engine, memory_manager, log_parser)
                    
                    import asyncio
                    
                    initial_state = {
                        "ticket_id": st.session_state.case_num,
                        "log_data": log_txt,
                        "status_updates": [],
                        "confidence_score": st.session_state.analysis_result.get("confidence_score", 0.0)
                    }
                    
                    final_state = {}
                    
                    async def run_log_analysis():
                        async for event in graph.workflow.astream(initial_state):
                            for node_name, output in event.items():
                                final_state.update(output)
                                if "status_updates" in output and output["status_updates"]:
                                    st.write(output["status_updates"][-1])
                    
                    asyncio.run(run_log_analysis())
                    
                    st.session_state.log_summary = final_state.get("log_summary")
                    st.session_state.enhanced_result = final_state.get("enhanced_rca")
                    status.update(label="Log Correlation Complete!", state="complete", expanded=False)
                st.rerun()
        
        if st.session_state.enhanced_result:
            st.markdown("---")
            e_res = st.session_state.enhanced_result
            col_e1, col_e2 = st.columns([3, 2])
            
            with col_e1:
                st.markdown("#### 🌟 Log-Enriched diagnosis")
                st.success(f"**Root Cause:** {e_res.get('enhanced_root_cause')}")
                st.markdown(f"**Recalibration Reason:** {e_res.get('confidence_change_reason')}")
                
                st.markdown("#### Actionable steps")
                e_steps = e_res.get("enhanced_resolution") or ""
                e_steps_list = e_steps if isinstance(e_steps, list) else e_steps.split(". ")
                
                # Group numbered markers with their steps
                processed_e_steps = []
                temp_e_step = ""
                for s in e_steps_list:
                    s = s.strip()
                    if not s: continue
                    if s.isdigit() and len(s) <= 2:
                        temp_e_step = s + ". "
                    else:
                        processed_e_steps.append(temp_e_step + s)
                        temp_e_step = ""
                
                for s in processed_e_steps:
                    st.markdown(f'<div class="action-card">🔥 {s.strip().strip(".")}</div>', unsafe_allow_html=True)
            
            with col_e2:
                st.markdown('<div style="text-align: center;">', unsafe_allow_html=True)
                st.markdown("#### Enhanced Confidence")
                confidence_gauge(e_res.get("enhanced_confidence_score", 0))
                st.markdown('</div>', unsafe_allow_html=True)

    with tab_audit:
        st.markdown("### Technical Evidence & Audit Trail")
        a1, a2, a3 = st.tabs(["Case JSON", "Vision Analytics", "Knowledge Base Match"])
        with a1: st.code(json.dumps(st.session_state.ticket_data, indent=2), language="json")
        with a2: 
            if st.session_state.vision_data: st.json(st.session_state.vision_data)
            else: st.write("No visual evidence detected.")
        with a3:
            if st.session_state.similar_match:
                # Filter out embedding for clean display
                match_data = st.session_state.similar_match[0].copy()
                match_data.pop("embedding", None)
                st.json(match_data)
            else: st.write("No similar historical patterns found.")

st.markdown("---")
st.caption("DebugGenie v2.1 Pro | High-Contrast investigative Dashboard")
