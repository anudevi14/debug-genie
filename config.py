import os
from dotenv import load_dotenv

# Load environment variables from .env file (force override to catch changes)
load_dotenv(override=True)

# Clear streamlit cache when config changes
try:
    import streamlit as st
    st.cache_resource.clear()
except ImportError:
    pass

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    SF_CLIENT_ID = os.getenv("SF_CLIENT_ID")
    SF_CLIENT_SECRET = os.getenv("SF_CLIENT_SECRET")
    SF_REFRESH_TOKEN = os.getenv("SF_REFRESH_TOKEN")
    SF_INSTANCE_URL = os.getenv("SF_INSTANCE_URL")
    MOCK_MODE = os.getenv("DEBUG_GENIE_MOCK_MODE", "false").lower() == "true"


    @classmethod
    def validate(cls):
        if cls.MOCK_MODE:
            return True
        missing = []
        for key in ["OPENAI_API_KEY", "SF_CLIENT_ID", "SF_CLIENT_SECRET", "SF_REFRESH_TOKEN", "SF_INSTANCE_URL"]:
            if not getattr(cls, key):
                missing.append(key)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}. Set DEBUG_GENIE_MOCK_MODE=true in .env to run with mock data.")


    @classmethod
    def get_openai_model(cls):
        # Using the specified gpt-4.1-mini model
        return "gpt-4.1-mini"
