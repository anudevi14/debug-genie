import streamlit as st
import json
import numpy as np
from config import Config
from salesforce_client import SalesforceClient
from ai_analyzer import AIAnalyzer
from similarity_engine import SimilarityEngine
from memory_manager import MemoryManager
from log_parser import LogParser

# Page Configuration
st.set_page_config(page_title="DebugGenie - AI Production Copilot", page_icon="🕵️")

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

# UI Layout
st.title("DebugGenie – AI Production Copilot")

if Config.MOCK_MODE:
    st.warning("⚠️ **Running in Mock Mode**: Data is hardcoded. Set `DEBUG_GENIE_MOCK_MODE=false` in `.env` to use real Salesforce data.")

st.markdown("Enter a Salesforce Ticket Number to generate a Root Cause Analysis (RCA).")

# Sidebar for Semantic Memory Management
with st.sidebar:
    st.header("🧠 Semantic Memory")
    if memory_manager:
        stats = memory_manager.get_memory_stats()
        st.write(f"Knowledge Base: **{stats['entry_count']}** tickets")
        st.write(f"Verified Patterns: **{stats['verified_count']}**")
        st.write(f"Avg Reliability: **{stats['avg_reliability']:.2f}**")
    
    if st.button("🔄 Sync & Backfill Memory"):
        if not sf_client:
            st.error("Salesforce client not initialized.")
        else:
            memory_manager.reload()
            with st.spinner("Fetching non-new tickets from Salesforce..."):
                historical_cases = sf_client.fetch_historical_cases(limit=100, filter_non_new=True)
                
            if not historical_cases:
                st.info("No historical tickets found to backfill.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                new_entries = []
                
                for i, case in enumerate(historical_cases):
                    case_num = case["CaseNumber"]
                    status_text.text(f"Processing #{case_num}...")
                    
                    if any(e["case_number"] == case_num for e in memory_manager.get_all_entries()):
                        progress_bar.progress((i + 1) / len(historical_cases))
                        continue
                    
                    text = sf_client.get_ticket_text_for_comparison(case)
                    embedding = ai_analyzer.get_embedding(text)
                    
                    new_entries.append({
                        "case_number": case_num,
                        "text": text,
                        "embedding": embedding,
                        "root_cause": "N/A (Historical)",
                        "resolution": "N/A (Historical)"
                    })
                    progress_bar.progress((i + 1) / len(historical_cases))
                
                if new_entries:
                    memory_manager.save_memory(new_entries)
                    st.success(f"Added {len(new_entries)} new tickets to semantic memory!")
                    st.rerun()
                else:
                    st.info("Semantic memory is already up to date.")

with st.form("analysis_form"):
    ticket_input = st.text_input("Salesforce Ticket Number", placeholder="e.g. 12345678")
    submit_button = st.form_submit_button("Analyze")

if submit_button:
    if not ticket_input:
        st.warning("Please enter a ticket number.")
    elif not sf_client or not ai_analyzer:
        st.error("System is not properly configured. Please check environment variables.")
    else:
        try:
            # Re-initialize state for new search
            st.session_state.update({
                "analysis_result": None,
                "case_num": ticket_input,
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

            # 1. Fetch Current Ticket
            with st.spinner(f"Fetching Ticket #{ticket_input}..."):
                ticket_data, case_obj = sf_client.get_full_ticket_data(ticket_input)
            
            if not ticket_data:
                st.error(f"Ticket #{ticket_input} not found in Salesforce.")
            else:
                st.session_state.ticket_data = ticket_data
                
                # 2. Handle Screenshots (Vision)
                with st.spinner("Checking for screenshot attachments..."):
                    attachments = sf_client.fetch_case_attachments(case_obj["Id"])
                
                if attachments:
                    attach = attachments[0]
                    with st.spinner(f"Extracting visual evidence from {attach['Name']}..."):
                        img_base64 = sf_client.get_attachment_content(attach["Id"], source=attach.get("Source", "Attachment"))
                        st.session_state.vision_data = ai_analyzer.vision_extract(img_base64, content_type=attach.get("ContentType", "image/jpeg"))
                
                # 3. Semantic Similarity Matching
                text_for_embedding = sf_client.get_ticket_text_for_comparison(case_obj)
                if st.session_state.vision_data:
                    text_for_embedding += f"\nVisual Markers: {json.dumps(st.session_state.vision_data)}"
                
                st.session_state.text_for_embedding = text_for_embedding
                
                with st.spinner("Searching semantic memory..."):
                    current_embedding = ai_analyzer.get_embedding(text_for_embedding)
                    st.session_state.current_embedding = current_embedding
                    memory_entries = memory_manager.get_all_entries()
                    similar_match, score = similarity_engine.find_most_similar_semantic(current_embedding, memory_entries)
                
                if similar_match:
                    st.session_state.similar_match = (similar_match, score)
                    st.session_state.hist_context = {
                        "ticket_number": similar_match['case_number'],
                        "score": round(float(score), 2),
                        "content": similar_match['text'],
                        "full_entry": similar_match
                    }

                # 4. Analyze with AI
                with st.spinner("Generating Explainable RCA..."):
                    st.session_state.analysis_result = ai_analyzer.analyze_ticket(
                        ticket_data, 
                        historical_context=st.session_state.hist_context, 
                        vision_data=st.session_state.vision_data
                    )
                
                # Auto-Register into Memory
                memory_manager.save_memory([{
                    "case_number": ticket_input,
                    "text": st.session_state.text_for_embedding,
                    "embedding": st.session_state.current_embedding,
                    "root_cause": st.session_state.analysis_result.get("probableRootCause"),
                    "resolution": st.session_state.analysis_result.get("recommendedSteps")
                }])

                st.rerun()
                    
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

# Display Results if they exist in session_state
if st.session_state.analysis_result:
    res = st.session_state.analysis_result
    
    # 📋 Header Indicators
    st.markdown("### 📋 Stage 1: Initial RCA Results")
    
    col_vis, col_mem = st.columns(2)
    if st.session_state.vision_data:
        col_vis.success("📸 Vision Findings Integrated")
        with col_vis.expander("Peek Visual Markers"):
            st.json(st.session_state.vision_data)
    if st.session_state.similar_match:
        col_mem.info(f"🧠 Matched Pattern: #{st.session_state.similar_match[0]['case_number']}")

    # Initial Confidence Meter
    conf_score = res.get("confidence_score", 0)
    conf_color = "green" if conf_score > 90 else ("orange" if conf_score > 70 else "red")
    st.progress(conf_score / 100)
    st.markdown(f"**Initial Confidence:** :{conf_color}[{conf_score}%]")
    
    with st.expander("Expand Initial RCA Details"):
        st.json(res)

    # 🚀 Phase 7: Log Enrichment Section
    st.markdown("---")
    st.subheader("🕵️ Deep Dive: Assisted Log Correlation")
    st.write("Provide Splunk logs to refine the analysis and validate technical evidence.")
    
    with st.expander("Upload/Paste Logs for Enhanced Analysis"):
        log_input = st.text_area("Paste Splunk Logs here...", height=150)
        log_file = st.file_uploader("Or upload log file", type=["log", "txt"])
        
        final_log_text = ""
        if log_input:
            final_log_text = log_input
        elif log_file:
            final_log_text = log_file.read().decode("utf-8")
            
        if st.button("🔍 Run Log-Enriched Re-Analysis"):
            if not final_log_text:
                st.warning("Please provide log content.")
            else:
                with st.spinner("Analyzing log patterns..."):
                    summary = log_parser.parse(final_log_text)
                    st.session_state.log_summary = summary
                
                if summary:
                    with st.spinner("Correlating logs with RCA..."):
                        log_summary_text = log_parser.format_for_ai(summary)
                        enhanced = ai_analyzer.reanalyze_with_logs(
                            st.session_state.ticket_data,
                            st.session_state.analysis_result,
                            log_summary_text,
                            vision_data=st.session_state.vision_data,
                            historical_context=st.session_state.hist_context
                        )
                        st.session_state.enhanced_result = enhanced
                    st.rerun()

    # 🌟 Display Enhanced Results
    if st.session_state.enhanced_result:
        e_res = st.session_state.enhanced_result
        st.markdown("### 🌟 Stage 2: Enhanced RCA (Log-Enriched)")
        
        e_conf = e_res.get("enhanced_confidence_score", 0)
        e_color = "green" if e_conf > 90 else ("orange" if e_conf > 70 else "red")
        
        st.progress(e_conf / 100)
        delta = e_conf - conf_score
        st.markdown(f"**Enhanced Confidence:** :{e_color}[{e_conf}%] ({'+' if delta >= 0 else ''}{delta}%)")
        st.info(f"**Reasoning Change:** {e_res.get('confidence_change_reason')}")

        st.json(e_res)
        
        if st.session_state.log_summary:
            with st.expander("Structured Log Insights"):
                st.json(st.session_state.log_summary)

    # Feedback Section
    st.markdown("---")
    st.subheader("📝 Analyst Feedback")
    if st.session_state.feedback_submitted:
        st.success("✅ Feedback successfully saved to knowledge base!")
    else:
        # feedback on final result
        final_rca = st.session_state.enhanced_result or st.session_state.analysis_result
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Outcome Correct"):
                fb_rca = {
                    "probableRootCause": final_rca.get("enhanced_root_cause") or final_rca.get("probableRootCause"),
                    "recommendedSteps": final_rca.get("enhanced_resolution") or final_rca.get("recommendedSteps")
                }
                memory_manager.submit_feedback(
                    st.session_state.case_num, "correct", fb_rca,
                    text=st.session_state.text_for_embedding,
                    embedding=st.session_state.current_embedding
                )
                st.session_state.feedback_submitted = True
                st.rerun()
        with col2:
            if st.button("❌ Outcome Incorrect"):
                fb_rca = {
                    "probableRootCause": final_rca.get("enhanced_root_cause") or final_rca.get("probableRootCause"),
                    "recommendedSteps": final_rca.get("enhanced_resolution") or final_rca.get("recommendedSteps")
                }
                memory_manager.submit_feedback(
                    st.session_state.case_num, "incorrect", fb_rca,
                    text=st.session_state.text_for_embedding,
                    embedding=st.session_state.current_embedding
                )
                st.session_state.feedback_submitted = True
                st.rerun()

st.markdown("---")
st.caption("Powered by Salesforce, Vision AI, and Splunk Correlation. Stage 2 Investigation Mode active.")
