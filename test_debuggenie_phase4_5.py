import unittest
from unittest.mock import patch, MagicMock
from ai_analyzer import AIAnalyzer
import json

class TestDebugGeniePhase45(unittest.TestCase):

    @patch('ai_analyzer.OpenAI')
    @patch('config.Config.OPENAI_API_KEY', 'fake_key')
    def test_confidence_output_schema(self, mock_openai_class):
        mock_client = mock_openai_class.return_value
        mock_response = MagicMock()
        mock_content = {
            "impactedService": "Payment-Gateway",
            "probableRootCause": "Timeout",
            "splunkQuerySuggestion": "query",
            "recommendedSteps": "Restart",
            "confidence": "High",
            "confidence_score": 92.5,
            "confidence_reasoning": "High similarity (0.91) and visual evidence confirms 504 error.",
            "isRepeatedIssue": True,
            "similarTicketReference": "00001001",
            "similarityScore": 0.91,
            "visualEvidenceUsed": True
        }
        mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_content)))]
        mock_client.chat.completions.create.return_value = mock_response

        analyzer = AIAnalyzer()
        result = analyzer.analyze_ticket("Test ticket", historical_context={"score": 0.91, "ticket_number": "00001001", "content": "..."})
        
        self.assertEqual(result["confidence_score"], 92.5)
        self.assertIn("similarity", result["confidence_reasoning"].lower())
        self.assertTrue(result["visualEvidenceUsed"])

    def test_validate_and_parse_defaults(self):
        analyzer = AIAnalyzer()
        # Missing confidence_score and confidence_reasoning
        incomplete_json = '{"impactedService": "Portal"}'
        result = analyzer._validate_and_parse(incomplete_json)
        
        self.assertEqual(result["confidence_score"], 50.0)
        self.assertEqual(result["confidence_reasoning"], "N/A")
        self.assertFalse(result["isRepeatedIssue"])

if __name__ == '__main__':
    unittest.main()
