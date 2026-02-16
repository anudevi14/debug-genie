import streamlit as st
import json
from config import Config
from salesforce_client import SalesforceClient
from ai_analyzer import AIAnalyzer

# Page Configuration
st.set_page_config(page_title="DebugGenie - AI Production Copilot", page_icon="🕵️")

# Initialize Clients
@st.cache_resource
def get_clients():
    try:
        Config.validate()
        return SalesforceClient(), AIAnalyzer()
    except Exception as e:
        st.error(f"Configuration Error: {e}")
        return None, None

sf_client, ai_analyzer = get_clients()

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
            with st.spinner(f"Fetching Ticket #{ticket_number}..."):
                ticket_data = sf_client.get_full_ticket_data(ticket_number)
            
            if not ticket_data:
                st.error(f"Ticket #{ticket_number} not found in Salesforce.")
            else:
                # Show fetched data overview
                st.info(f"✅ Fetched Ticket: **#{ticket_number}**")
                with st.expander("Show Fetched Case Details (Input to AI)"):
                    st.text(ticket_data)

                with st.spinner("Analyzing with GPT-4.1-mini..."):
                    analysis_result = ai_analyzer.analyze_ticket(ticket_data)
                
                st.success("Analysis Complete!")
                st.subheader("Root Cause Analysis (RCA)")
                st.json(analysis_result)
                
                # Optional: Detailed View
                with st.expander("View Raw Analysis Data"):
                    st.write(analysis_result)
                    
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

# Footer
st.markdown("---")
st.caption("Powered by Salesforce REST API and OpenAI GPT-4.1-mini.")
