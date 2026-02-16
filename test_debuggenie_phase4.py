import unittest
from unittest.mock import patch, MagicMock
from ai_analyzer import AIAnalyzer
from salesforce_client import SalesforceClient
import json

class TestDebugGeniePhase4(unittest.TestCase):

    @patch('ai_analyzer.OpenAI')
    @patch('config.Config.OPENAI_API_KEY', 'fake_key')
    def test_vision_extract(self, mock_openai_class):
        mock_client = mock_openai_class.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"error_message": "500 Internal Server Error", "error_code": "500"}'))]
        mock_client.chat.completions.create.return_value = mock_response

        analyzer = AIAnalyzer()
        result = analyzer.vision_extract("fake_base64")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["error_message"], "500 Internal Server Error")
        mock_client.chat.completions.create.assert_called_once()

    @patch('ai_analyzer.OpenAI')
    @patch('config.Config.OPENAI_API_KEY', 'fake_key')
    def test_multimodal_analysis_prompt(self, mock_openai_class):
        mock_client = mock_openai_class.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"impactedService": "Auth", "probableRootCause": "Visual error match", "splunkQuerySuggestion": "index=logs", "recommendedSteps": "Check logs", "confidence": "High", "isRepeatedIssue": false, "similarTicketReference": "N/A", "similarityScore": 0.0, "visualEvidenceUsed": true}'))]
        mock_client.chat.completions.create.return_value = mock_response

        analyzer = AIAnalyzer()
        vision_data = {"error_message": "Timeout"}
        result = analyzer.analyze_ticket("Case content", vision_data=vision_data)
        
        self.assertTrue(result["visualEvidenceUsed"])
        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args.kwargs['messages'][1]['content']
        self.assertIn("VISUAL EVIDENCE", user_msg)
        self.assertIn("Timeout", user_msg)

    @patch('salesforce_client.requests.get')
    def test_fetch_case_attachments_mock(self, mock_get):
        # Setting up the mock response for Salesforce query
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"records": [{"Id": "att1", "Name": "test.jpg"}]}
        mock_get.return_value = mock_response

        client = SalesforceClient()
        # Mocking authentication to avoid hitting API
        client.access_token = "fake_access_token"
        client.instance_url = "https://fake.salesforce.com"
        
        attachments = client.fetch_case_attachments("case123")
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["Name"], "test.jpg")

if __name__ == '__main__':
    unittest.main()
