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

    def fetch_historical_cases(self, current_ticket_number=None, limit=50, filter_non_new=True):
        """Fetch last N cases excluding the current one, optionally filtering for non-new status."""
        where_clause = []
        if current_ticket_number:
            where_clause.append(f"CaseNumber != '{current_ticket_number}'")
        
        if filter_non_new:
            where_clause.append("Status != 'New'")
            
        where_str = " AND ".join(where_clause) if where_clause else "Id != NULL"
        
        soql = (
            f"SELECT Id, CaseNumber, Subject, Description, CreatedDate "
            f"FROM Case WHERE {where_str} "
            f"ORDER BY CreatedDate DESC LIMIT {limit}"
        )
        url = f"{self.instance_url}/services/data/v59.0/query"
        params = {"q": soql}

        if Config.MOCK_MODE:
            return [
                {"Id": "mock_1", "CaseNumber": "00001006", "Subject": "Payment Gateway Timeout", "Description": "504 errors in payment service."},
                {"Id": "mock_2", "CaseNumber": "00001007", "Subject": "User Login Failure", "Description": "Cannot login to dashboard."}
            ]

        response = requests.get(url, headers=self._get_headers(), params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch historical cases: {response.text}")
        
        return response.json().get("records", [])

    def get_ticket_text_for_comparison(self, case_record):
        """Extracts and concatenates Case details for similarity check."""
        subject = case_record.get("Subject", "")
        description = case_record.get("Description", "")
        return f"{subject} {description}".strip()

    def get_full_ticket_data(self, ticket_number):
        """Combines Case details and comments into a single text block for analysis."""
        case = self.fetch_case(ticket_number)
        if not case:
            return None
        
        comments = self.fetch_case_comments(case["Id"])
        
        combined_text = f"Subject: {case.get('Subject')}\n"
        combined_text += f"Description: {case.get('Description')}\n"
        combined_text += f"Comments:\n{comments}"
        
        return combined_text, case # Returning case object as well for ID/Number access

    def fetch_case_attachments(self, case_id):
        """Fetch image attachments (JPG/JPEG) for a given Case Id."""
        soql = (
            f"SELECT Id, Name, ContentType FROM Attachment "
            f"WHERE ParentId = '{case_id}' "
            f"AND (ContentType = 'image/jpeg' OR ContentType = 'image/jpg') "
            f"LIMIT 1"
        )
        url = f"{self.instance_url}/services/data/v59.0/query"
        params = {"q": soql}

        if Config.MOCK_MODE:
            return [{"Id": "mock_attach_id", "Name": "error_screenshot.jpg", "ContentType": "image/jpeg"}]

        response = requests.get(url, headers=self._get_headers(), params=params)
        if response.status_code != 200:
            return [] # Silent fail for attachments to not break RCA pipeline
        
        return response.json().get("records", [])

    def get_attachment_content(self, attachment_id):
        """Retrieve base64 content of a specific attachment."""
        url = f"{self.instance_url}/services/data/v59.0/sobjects/Attachment/{attachment_id}/Body"
        
        if Config.MOCK_MODE:
            return "mock_base64_content"

        response = requests.get(url, headers=self._get_headers())
        if response.status_code != 200:
            return None
            
        import base64
        return base64.b64encode(response.content).decode('utf-8')
