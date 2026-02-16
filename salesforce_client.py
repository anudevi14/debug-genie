import requests
from config import Config

class SalesforceClient:
    def __init__(self):
        self.access_token: str | None = None

        self.instance_url = Config.SF_INSTANCE_URL

    def authenticate(self):
        """Obtain access token using refresh token flow."""
        # Ensure we use the base instance URL for the token endpoint
        url = f"{self.instance_url.rstrip('/')}/services/oauth2/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": Config.SF_CLIENT_ID,
            "client_secret": Config.SF_CLIENT_SECRET,
            "refresh_token": Config.SF_REFRESH_TOKEN
        }
        
        if Config.MOCK_MODE:
            self.access_token = "mock_access_token"
            return self.access_token

        response = requests.post(url, data=payload)

        if response.status_code != 200:
            raise Exception(f"Salesforce Authentication Failed: {response.text}")
        
        data = response.json()
        self.access_token = data.get("access_token")
        
        # Salesforce often returns a specific instance_url in the token response (e.g. if using login.salesforce.com)
        if data.get("instance_url"):
            self.instance_url = data.get("instance_url").rstrip('/')
            
        return self.access_token

    def _get_headers(self):
        if not self.access_token:
            self.authenticate()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def fetch_case(self, ticket_number, retry=True):
        """Fetch Case details by CaseNumber with automatic session refresh."""
        soql = f"SELECT Id, CaseNumber, Subject, Description FROM Case WHERE CaseNumber = '{ticket_number}'"
        url = f"{self.instance_url}/services/data/v59.0/query"
        params = {"q": soql}
        
        if Config.MOCK_MODE:
            return {"Id": "mock_case_id", "CaseNumber": ticket_number, "Subject": "Database Connectivity Issue", "Description": "Users reporting 504 Gateway Timeout when accessing the payments module."}

        response = requests.get(url, headers=self._get_headers(), params=params)

        # Handle expired session
        if response.status_code == 401 and retry:
            self.access_token = None # Force refresh
            return self.fetch_case(ticket_number, retry=False)

        if response.status_code != 200:
            raise Exception(f"Failed to fetch case: {response.text}")
        
        records = response.json().get("records", [])
        if not records:
            return None
        return records[0]

    def fetch_case_comments(self, case_id, retry=True):
        """Fetch all related CaseComments for a given Case Id with automatic session refresh."""
        soql = f"SELECT CommentBody FROM CaseComment WHERE ParentId = '{case_id}'"
        url = f"{self.instance_url}/services/data/v59.0/query"
        params = {"q": soql}
        
        if Config.MOCK_MODE:
            return "2026-02-16 10:00: Logs show connection pool exhaustion in the Auth service.\n2026-02-16 10:30: Restarted the service but issue persisted."

        response = requests.get(url, headers=self._get_headers(), params=params)

        # Handle expired session
        if response.status_code == 401 and retry:
            self.access_token = None # Force refresh
            return self.fetch_case_comments(case_id, retry=False)

        if response.status_code != 200:
            raise Exception(f"Failed to fetch case comments: {response.text}")
        
        records = response.json().get("records", [])
        comments = [rec["CommentBody"] for rec in records if rec.get("CommentBody")]
        return "\n".join(comments)

    def get_full_ticket_data(self, ticket_number):
        """Combines Case details and comments into a single text block for analysis."""
        case = self.fetch_case(ticket_number)
        if not case:
            return None
        
        comments = self.fetch_case_comments(case["Id"])
        
        combined_text = f"Subject: {case.get('Subject')}\n"
        combined_text += f"Description: {case.get('Description')}\n"
        combined_text += f"Comments:\n{comments}"
        
        return combined_text
