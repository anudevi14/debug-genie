# DebugGenie – AI Production Copilot

DebugGenie is an AI-powered production support tool that helps engineers perform rapid Root Cause Analysis (RCA) on Salesforce tickets. By combining real-time data from Salesforce with the advanced reasoning of OpenAI's GPT-4.1-mini, DebugGenie provides structured insights, probable causes, and even suggested Splunk queries to accelerate troubleshooting.

## 🚀 Features

- **Automated RCA**: Enter a Salesforce Ticket Number and get an AI-generated analysis in seconds.
- **Salesforce Integration**: Real-time fetching of Case descriptions and related Case Comments.
- **Structured JSON Output**: Standardized reports including impacted services, root cause, and recommended steps.
- **Secure Configuration**: Uses OAuth 2.0 Refresh Token flow and environment variables to keep credentials safe.

## 🛠️ Technology Stack

- **Python**: Core logic and backend.
- **Streamlit**: Modern, interactive UI.
- **Salesforce REST API**: OAuth 2.0 (Refresh Token Flow).
- **OpenAI API**: GPT-4.1-mini for high-accuracy analysis.

## 📋 Prerequisites

- Python 3.8+
- Salesforce Connected App (with `api` and `refresh_token` scopes)
- OpenAI API Key

## ⚙️ Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/anudevi14/debug-genie.git
   cd debug-genie
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Create a `.env` file in the root directory and add your credentials:
   ```env
   OPENAI_API_KEY=your_openai_api_key
   SF_CLIENT_ID=your_salesforce_client_id
   SF_CLIENT_SECRET=your_salesforce_client_secret
   SF_REFRESH_TOKEN=your_salesforce_refresh_token
   SF_INSTANCE_URL=https://your-instance.my.salesforce.com
   DEBUG_GENIE_MOCK_MODE=false
   ```

4. **Run the Application**
   ```bash
   python -m streamlit run app.py
   ```

## 🧪 Running Tests

A mocked test suite is provided to verify the integration logic without requiring active API connections:
```bash
python test_debuggenie.py
```

## 📄 License
MIT
