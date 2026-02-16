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
    st.write(f"Verified Patterns: **{stats['verified_count']}**")
    st.write(f"Avg Reliability: **{stats['avg_reliability']:.2f}**")
    
    if st.button("🔄 Sync & Backfill Memory"):
        if not sf_client:
            st.error("Salesforce client not initialized.")
        else:
            # Force reload to handle manual file deletions
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
                # 2. Handle Screenshots (Vision)
                vision_data = None
                with st.spinner("Checking for screenshot attachments..."):
                    attachments = sf_client.fetch_case_attachments(case_obj["Id"])
                
                if attachments:
                    attach = attachments[0]
                    st.info(f"📸 **Screenshot Found**: {attach['Name']} (Analyzing with Vision...)")
                    with st.spinner("Extracting visual evidence using GPT-4o Vision..."):
                        img_base64 = sf_client.get_attachment_content(attach["Id"], source=attach.get("Source", "Attachment"))
                        vision_data = ai_analyzer.vision_extract(img_base64, content_type=attach.get("ContentType", "image/jpeg"))
                    
                    if vision_data:
                        st.success("✅ Vision Analysis Complete!")
                        with st.expander("Show Extracted Visual Markers"):
                            st.json(vision_data)
                
                # 3. Semantic Similarity Matching
                text_for_embedding = sf_client.get_ticket_text_for_comparison(case_obj)
                if vision_data:
                    text_for_embedding += f"\nScreenshot Visual Markers: {json.dumps(vision_data)}"

                with st.spinner("Searching semantic memory for similar patterns..."):
                    current_embedding = ai_analyzer.get_embedding(text_for_embedding)
                    memory_entries = memory_manager.get_all_entries()
                    similar_match, score = similarity_engine.find_most_similar_semantic(current_embedding, memory_entries)
                
                # Intelligence Signal Prep
                hist_context = None
                if similar_match:
                    st.info(f"🧠 **Semantic Match Found**: #{similar_match['case_number']} (Confidence: {score:.1%})")
                    hist_context = {
                        "ticket_number": similar_match['case_number'],
                        "score": round(float(score), 2),
                        "content": similar_match['text'],
                        "full_entry": similar_match # Passing full entry for Phase 5 signals
                    }

                # 4. Analyze with AI (Explainable + Reliability Aware)
                with st.spinner("Generating Explainable RCA with GPT-4o..."):
                    analysis_result = ai_analyzer.analyze_ticket(
                        ticket_data, 
                        historical_context=hist_context, 
                        vision_data=vision_data
                    )
                
                st.success("Analysis Complete!")
                
                # Save result in session state for feedback
                st.session_state["last_analysis"] = analysis_result
                st.session_state["last_case_number"] = ticket_number
                
                # Confidence Meter Section
                conf_score = analysis_result.get("confidence_score", 0)
                if conf_score > 90:
                    conf_color = "green"
                    st.balloons()
                elif conf_score > 70:
                    conf_color = "orange"
                else:
                    conf_color = "red"
                
                st.subheader("Analysis Confidence")
                st.progress(conf_score / 100)
                st.markdown(f"**Confidence Score:** :{conf_color}[{conf_score}%]")
                
                with st.expander("Why this confidence level? (Explainability reasoning)"):
                    st.write(analysis_result.get("confidence_reasoning"))
                    st.write("---")
                    st.write("**Signals used:**")
                    st.write(f"- Semantic Similarity: {analysis_result.get('similarityScore', 0.0)}")
                    st.write(f"- Vision Evidence Found: {'Yes' if vision_data else 'No'}")
                    if similar_match:
                        st.write(f"- Linked Historical Match: #{similar_match['case_number']}")
                        st.write(f"- Historical Verified: {'✅' if similar_match.get('verified') else '❌'}")
                        st.write(f"- Historical Reliability: {similar_match.get('reliability_score', 0.7)}")

                # RCA Results
                st.subheader("Root Cause Analysis (RCA)")
                if analysis_result.get("isRepeatedIssue"):
                    st.error(f"🚨 **Repeated Issue Detected!** (Matches #{analysis_result.get('similarTicketReference')})")
                
                st.json(analysis_result)
                
                # Phase 5: Feedback Section
                st.markdown("---")
                st.subheader("📝 Analyst Feedback")
                st.write("Help DebugGenie improve by validating this analysis.")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✅ Correct"):
                        memory_manager.submit_feedback(
                            ticket_number, "correct", analysis_result,
                            confidence_score=conf_score
                        )
                        st.success("Feedback recorded! Confidence in this pattern increased.")
                with col2:
                    if st.button("❌ Incorrect"):
                        memory_manager.submit_feedback(
                            ticket_number, "incorrect", analysis_result,
                            confidence_score=conf_score
                        )
                        st.warning("Feedback recorded. Confidence in this pattern reduced.")
                
                with st.expander("✏️ Correct Details (Edit RCA)"):
                    with st.form("feedback_form"):
                        corrected_rc = st.text_area("Corrected Root Cause", value=analysis_result.get("probableRootCause"))
                        corrected_res = st.text_area("Corrected Resolution", value=analysis_result.get("recommendedSteps"))
                        if st.form_submit_button("Submit Correction"):
                            memory_manager.submit_feedback(
                                ticket_number, "edited", analysis_result,
                                analyst_correction={"root_cause": corrected_rc, "resolution": corrected_res},
                                confidence_score=conf_score
                            )
                            st.success("Correction saved! This version will be prioritized in the future.")

                # Debug Views
                with st.expander("View Input Data & Source Evidence"):
                    st.write("**Raw Ticket Data:**")
                    st.text(ticket_data)
                    if vision_data:
                        st.write("**Visual Evidence:**")
                        st.json(vision_data)
                    
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

# Footer
st.markdown("---")
st.caption("Powered by Salesforce, GPT-4o Vision, and OpenAI. Self-Improving Memory Phase 5 enabled.")
