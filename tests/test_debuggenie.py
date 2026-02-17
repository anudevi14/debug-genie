import unittest
from unittest.mock import patch, MagicMock
from src.clients.salesforce_client import SalesforceClient
from src.agents.ai_analyzer import AIAnalyzer
from src.config import Config

class TestDebugGenie(unittest.TestCase):

    @patch('src.clients.salesforce_client.requests.post')
    def test_sf_authentication(self, mock_post):
        # Mock successful authentication
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "mock_access_token"}
        mock_post.return_value = mock_response

        client = SalesforceClient()
        token = client.authenticate()
        
        self.assertEqual(token, "mock_access_token")
        self.assertEqual(client.access_token, "mock_access_token")

    @patch('src.clients.salesforce_client.requests.get')
    def test_sf_fetch_case(self, mock_get):
        # Mock successful case retrieval
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "records": [{"Id": "50000000001", "CaseNumber": "12345", "Subject": "Test Case", "Description": "Test Desc"}]
        }
        mock_get.return_value = mock_response

        client = SalesforceClient()
        client.access_token = "mock_token"
        case = client.fetch_case("12345")
        
        self.assertIsNotNone(case)
        self.assertEqual(case["CaseNumber"], "12345")

    @patch('src.agents.ai_analyzer.OpenAI')
    def test_ai_analysis(self, mock_openai_class):
        # Mock OpenAI response
        mock_client = mock_openai_class.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"impactedService": "Auth", "probableRootCause": "Expired", "splunkQuerySuggestion": "index=logs", "recommendedSteps": "Renew", "confidence": "High"}'))]
        mock_client.chat.completions.create.return_value = mock_response

        analyzer = AIAnalyzer()
        result = analyzer.analyze_ticket("Some ticket data")
        
        self.assertEqual(result["impactedService"], "Auth")
        self.assertEqual(result["confidence"], "High")

if __name__ == '__main__':
    unittest.main()
