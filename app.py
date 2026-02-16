import streamlit as st
import json
import numpy as np
from config import Config
from salesforce_client import SalesforceClient
from ai_analyzer import AIAnalyzer
from similarity_engine import SimilarityEngine
from memory_manager import MemoryManager

# Page Configuration
st.set_page_config(page_title="DebugGenie - AI Production Copilot", page_icon="🕵️")

# Initialize Clients
@st.cache_resource
def get_clients():
    try:
        Config.validate()
        return SalesforceClient(), AIAnalyzer(), SimilarityEngine(), MemoryManager()
    except Exception as e:
        st.error(f"Configuration Error: {e}")
        return None, None, None, None

sf_client, ai_analyzer, similarity_engine, memory_manager = get_clients()

# UI Layout
st.title("DebugGenie – AI Production Copilot")

if Config.MOCK_MODE:
    st.warning("⚠️ **Running in Mock Mode**: Data is hardcoded. Set `DEBUG_GENIE_MOCK_MODE=false` in `.env` to use real Salesforce data.")

st.markdown("Enter a Salesforce Ticket Number to generate a Root Cause Analysis (RCA).")

# Sidebar for Semantic Memory Management
with st.sidebar:
    st.header("🧠 Semantic Memory")
    stats = memory_manager.get_memory_stats()
    st.write(f"Knowledge Base: **{stats['entry_count']}** tickets")
    
    if st.button("🔄 Sync & Backfill Memory"):
        if not sf_client:
            st.error("Salesforce client not initialized.")
        else:
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
                    
                    # Check if already in memory
                    if any(e["case_number"] == case_num for e in memory_manager.get_all_entries()):
                        progress_bar.progress((i + 1) / len(historical_cases))
                        continue
                    
                    # Generate search text and embedding
                    text = sf_client.get_ticket_text_for_comparison(case)
                    embedding = ai_analyzer.get_embedding(text)
                    
                    new_entries.append({
                        "case_number": case_num,
                        "text": text,
                        "embedding": embedding,
                        "root_cause": "N/A (Historical)", # In future, GPT can pre-analyze
                        "resolution": "N/A (Historical)"
                    })
                    progress_bar.progress((i + 1) / len(historical_cases))
                
                if new_entries:
                    memory_manager.save_memory(new_entries)
                    st.success(f"Added {len(new_entries)} new tickets to semantic memory!")
                else:
                    st.info("Semantic memory is already up to date.")

with st.form("analysis_form"):
    ticket_number = st.text_input("Salesforce Ticket Number", placeholder="e.g. 12345678")
    submit_button = st.form_submit_button("Analyze")

if submit_button:
    if not ticket_number:
        st.warning("Please enter a ticket number.")
    elif not sf_client or not ai_analyzer:
        st.error("System is not properly configured. Please check environment variables.")
    else:
        try:
            # 1. Fetch Current Ticket
            with st.spinner(f"Fetching Ticket #{ticket_number}..."):
                ticket_data, case_obj = sf_client.get_full_ticket_data(ticket_number)
            
            if not ticket_data:
                st.error(f"Ticket #{ticket_number} not found in Salesforce.")
            else:
                # 2. Semantic Similarity Matching
                with st.spinner("Searching semantic memory for similar patterns..."):
                    current_text = sf_client.get_ticket_text_for_comparison(case_obj)
                    current_embedding = ai_analyzer.get_embedding(current_text)
                    
                    memory_entries = memory_manager.get_all_entries()
                    similar_match, score = similarity_engine.find_most_similar_semantic(current_embedding, memory_entries)
                
                # UI Indicator for Similarity
                hist_context = None
                if similar_match:
                    st.info(f"🧠 **Semantic Match Found**: #{similar_match['case_number']} (Confidence: {score:.1%})")
                    with st.expander("View Similar Historical Pattern"):
                        st.write(f"**Description Snippet:** {similar_match['text'][:500]}...")
                    
                    hist_context = {
                        "ticket_number": similar_match['case_number'],
                        "score": round(float(score), 2),
                        "content": similar_match['text']
                    }

                # Show fetched data overview
                st.info(f"✅ Fetched Ticket: **#{ticket_number}**")
                with st.expander("Show Fetched Case Details (Input to AI)"):
                    st.text(ticket_data)

                # 3. Analyze with AI
                with st.spinner("Analyzing with GPT-4.1-mini..."):
                    analysis_result = ai_analyzer.analyze_ticket(ticket_data, historical_context=hist_context)
                
                st.success("Analysis Complete!")
                
                # High-level Badge for Repeated Issues
                if analysis_result.get("isRepeatedIssue"):
                    st.error(f"🚨 **Repeated Issue Detected!** (Matches #{analysis_result.get('similarTicketReference')})")

                st.subheader("Root Cause Analysis (RCA)")
                st.json(analysis_result)
                
                # Optional: Detailed View
                with st.expander("View Raw Analysis Data"):
                    st.write(analysis_result)
                    
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

# Footer
st.markdown("---")
st.caption("Powered by Salesforce, OpenAI Embeddings, and GPT-4.1-mini. Semantic Phase 3 enabled.")
