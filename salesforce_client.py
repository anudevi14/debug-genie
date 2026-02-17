import requests
import json
import base64
from config import Config


class SalesforceClient:
    def __init__(self):
        self.client_id = Config.SF_CLIENT_ID
        self.client_secret = Config.SF_CLIENT_SECRET
        self.refresh_token = Config.SF_REFRESH_TOKEN
        self.instance_url = Config.SF_INSTANCE_URL
        self.access_token = None

    def _get_access_token(self):
        """Standard OAuth 2.0 Refresh Token Flow."""
        url = f"{self.instance_url}/services/oauth2/token"
        payload = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        try:
            response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()
            self.access_token = response.json().get('access_token')
            return self.access_token
        except Exception as e:
            print(f"Salesforce Auth Failed: {e}")
            return None

    def get_full_ticket_data(self, ticket_number):
        """Fetch Case details and related CaseComments."""
        if Config.MOCK_MODE:
            return self._get_mock_ticket_data(ticket_number)

        case_obj = self.fetch_case(ticket_number)
        if not case_obj:
            return None, None

        case_id = case_obj['Id']
        comments_list = self.fetch_case_comments(case_id)

        # Compile context
        full_context = f"TICKET: {case_obj['CaseNumber']}\n"
        full_context += f"SUBJECT: {case_obj['Subject']}\n"
        full_context += f"DESCRIPTION: {case_obj['Description']}\n\n"
        full_context += "COMMENTS:\n"
        if isinstance(comments_list, list):
            for c in comments_list:
                full_context += f"- [{c.get('CreatedDate', 'N/A')}] {c.get('CommentBody', 'N/A')}\n"
        else:
            full_context += comments_list

        return full_context, case_obj

    def fetch_case(self, ticket_number):
        """Fetch Case details by CaseNumber."""
        soql = f"SELECT Id, CaseNumber, Subject, Description FROM Case WHERE CaseNumber = '{ticket_number}' LIMIT 1"
        data = self._query_salesforce(soql)
        if data and data.get('records'):
            return data['records'][0]
        return None

    def fetch_case_comments(self, case_id):
        """Fetch all related CaseComments for a given Case Id."""
        soql = f"SELECT CommentBody, CreatedDate FROM CaseComment WHERE ParentId = '{case_id}' ORDER BY CreatedDate DESC"
        data = self._query_salesforce(soql)
        return data.get('records', [])

    def fetch_historical_cases(self, limit=50, filter_non_new=True):
        """Fetches historical cases for backfilling semantic memory."""
        if Config.MOCK_MODE:
            return [
                {"Id": "m1", "CaseNumber": "1001", "Subject": "Payment 504", "Description": "Gateway timeout in prod."},
                {"Id": "m2", "CaseNumber": "1002", "Subject": "Login issue", "Description": "Users can't login with SSO."}
            ]

        status_filter = "WHERE Status != 'New'" if filter_non_new else ""
        soql = f"SELECT Id, CaseNumber, Subject, Description FROM Case {status_filter} ORDER BY CreatedDate DESC LIMIT {limit}"
        data = self._query_salesforce(soql)
        return data.get("records", [])

    def fetch_case_attachments(self, case_id):
        """Fetch image attachments for a given Case Id."""
        if Config.MOCK_MODE:
            return [{"Id": "mock_attach_id", "Name": "error_screenshot.jpg", "ContentType": "image/jpeg", "Source": "Attachment"}]

        # Try legacy Attachment object
        soql_attach = (
            f"SELECT Id, Name, ContentType FROM Attachment "
            f"WHERE ParentId = '{case_id}' "
            f"AND (ContentType IN ('image/jpeg', 'image/jpg', 'image/png')) "
            f"LIMIT 1"
        )
        attach_data = self._query_salesforce(soql_attach)
        if attach_data and attach_data.get("records"):
            records = attach_data["records"]
            for r in records:
                r["Source"] = "Attachment"
            return records

        # Try modern ContentDocumentLink
        soql_cdl = f"SELECT ContentDocumentId FROM ContentDocumentLink WHERE LinkedEntityId = '{case_id}'"
        cdl_data = self._query_salesforce(soql_cdl)
        if cdl_data and cdl_data.get("records"):
            doc_ids = [f"'{r['ContentDocumentId']}'" for r in cdl_data["records"]]
            soql_cv = (
                f"SELECT Id, Title, FileExtension, FileType FROM ContentVersion "
                f"WHERE ContentDocumentId IN ({','.join(doc_ids)}) "
                f"AND IsLatest = true "
                f"AND FileExtension IN ('jpg', 'jpeg', 'png') "
                f"LIMIT 1"
            )
            cv_data = self._query_salesforce(soql_cv)
            if cv_data and cv_data.get("records"):
                cv = cv_data["records"][0]
                return [{
                    "Id": cv["Id"],
                    "Name": f"{cv['Title']}.{cv['FileExtension']}",
                    "ContentType": f"image/{cv['FileExtension'].lower()}",
                    "Source": "ContentVersion"
                }]

        return []

    def get_attachment_content(self, attachment_id, source="Attachment"):
        """Retrieve base64 content of a specific attachment."""
        if Config.MOCK_MODE:
            return "dmlydHVhbF9pbWFnZV9kYXRh"

        if source == "Attachment":
            url = f"{self.instance_url}/services/data/v60.0/sobjects/Attachment/{attachment_id}/Body"
        else:
            url = f"{self.instance_url}/services/data/v60.0/sobjects/ContentVersion/{attachment_id}/VersionData"

        if not self.access_token:
            self._get_access_token()

        headers = {'Authorization': f'Bearer {self.access_token}'}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return base64.b64encode(response.content).decode('utf-8')
        except Exception as e:
            print(f"Failed to download attachment: {e}")
            return None

    def get_ticket_text_for_comparison(self, case_obj):
        """Helper to create a single string for semantic similarity."""
        return f"{case_obj.get('Subject', '')} {case_obj.get('Description', '')}".strip()

    def _query_salesforce(self, soql):
        """Internal helper for SOQL queries."""
        if not self.access_token:
            self._get_access_token()

        url = f"{self.instance_url}/services/data/v60.0/query"
        params = {'q': soql}
        headers = {'Authorization': f'Bearer {self.access_token}'}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Salesforce Query Failed: {e}")
            return None

    def _get_mock_ticket_data(self, ticket_number):
        """Return hardcoded data for demonstration if SF credentials aren't set."""
        mock_case = {
            "Id": "MOCK_504_ID",
            "CaseNumber": ticket_number,
            "Subject": "URGENT: Payments failing with 504 Gateway Timeout in Checkout",
            "Description": "Started at 08:30 UTC. checkout-service is throwing 504 errors for all credit card transactions. No recent deployments.",
            "Status": "Working",
            "Priority": "High",
            "CreatedDate": "2024-05-15T08:35:00.000+0000"
        }
        full_context = f"TICKET: {mock_case['CaseNumber']}\n"
        full_context += f"SUBJECT: {mock_case['Subject']}\n"
        full_context += f"DESCRIPTION: {mock_case['Description']}\n\n"
        full_context += "COMMENTS:\n"
        full_context += "- [2024-05-15T08:40:00] Initial investigation shows DB connection pool is saturated.\n"
        full_context += "- [2024-05-15T08:45:00] Seeing spike in thread count in checkout-service."

        return full_context, mock_case
