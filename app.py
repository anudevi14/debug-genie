import streamlit as st
import json
from config import Config
from salesforce_client import SalesforceClient
from ai_analyzer import AIAnalyzer
from similarity_engine import SimilarityEngine

# Page Configuration
st.set_page_config(page_title="DebugGenie - AI Production Copilot", page_icon="🕵️")

# Initialize Clients
@st.cache_resource
def get_clients():
    try:
        Config.validate()
        return SalesforceClient(), AIAnalyzer(), SimilarityEngine()
    except Exception as e:
        st.error(f"Configuration Error: {e}")
        return None, None, None

sf_client, ai_analyzer, similarity_engine = get_clients()

# UI Layout
st.title("DebugGenie – AI Production Copilot")

if Config.MOCK_MODE:
    st.warning("⚠️ **Running in Mock Mode**: Data is hardcoded. Set `DEBUG_GENIE_MOCK_MODE=false` in `.env` to use real Salesforce data.")

st.markdown("Enter a Salesforce Ticket Number to generate a Root Cause Analysis (RCA).")

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
                # 2. Fetch Historical Tickets & Check Similarity
                with st.spinner("Searching for similar historical tickets..."):
                    historical_tickets = sf_client.fetch_historical_cases(ticket_number)
                    current_text = sf_client.get_ticket_text_for_comparison(case_obj)
                    similar_match, score = similarity_engine.find_most_similar(current_text, historical_tickets, sf_client)
                
                # UI Indicator for Similarity
                hist_context = None
                if similar_match:
                    st.warning(f"⚠️ **Similar Ticket Found**: #{similar_match['CaseNumber']} (Similarity: {score:.1%})")
                    with st.expander("View Similar Ticket Details"):
                        st.write(f"**Subject:** {similar_match['Subject']}")
                        st.write(f"**Description:** {similar_match['Description']}")
                    
                    hist_context = {
                        "ticket_number": similar_match['CaseNumber'],
                        "score": round(score, 2),
                        "content": sf_client.get_ticket_text_for_comparison(similar_match)
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
st.caption("Powered by Salesforce REST API and OpenAI GPT-4.1-mini. Intelligence Phase 2 enabled.")
