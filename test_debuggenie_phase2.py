import unittest
from unittest.mock import patch, MagicMock
from salesforce_client import SalesforceClient
from ai_analyzer import AIAnalyzer
from similarity_engine import SimilarityEngine
from config import Config

class TestDebugGeniePhase2(unittest.TestCase):

    def test_similarity_score(self):
        engine = SimilarityEngine(threshold=0.6)
        text1 = "Payment gateway 504 timeout"
        text2 = "Payment gateway 504 error"
        text3 = "User login failure"

        score12 = engine._calculate_score(text1, text2)
        score13 = engine._calculate_score(text1, text3)

        self.assertGreater(score12, 0.7)
        self.assertLess(score13, 0.4)

    @patch('salesforce_client.SalesforceClient')
    def test_find_most_similar(self, mock_sf_client):
        engine = SimilarityEngine(threshold=0.6)
        current_text = "Database connection pool exhaustion and 504 gateway timeout"
        
        historical_tickets = [
            {"Id": "h1", "CaseNumber": "001", "Subject": "Database connection pool exhaustion", "Description": "504 gateway timeout errors detected in payments service."},
            {"Id": "h2", "CaseNumber": "002", "Subject": "OOM Error", "Description": "Memory leak."}
        ]
        
        # Mocking the client method used for text extraction
        mock_sf_client.get_ticket_text_for_comparison.side_effect = lambda x: f"{x['Subject']} {x['Description']}"

        match, score = engine.find_most_similar(current_text, historical_tickets, mock_sf_client)
        print(f"DEBUG: Similarity Score: {score}")

        self.assertIsNotNone(match, f"Expected a match but got None. Score was: {score}")
        self.assertEqual(match["CaseNumber"], "001")
        self.assertGreater(score, 0.6)

    @patch('ai_analyzer.OpenAI')
    def test_ai_analysis_with_context(self, mock_openai_class):
        mock_client = mock_openai_class.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"impactedService": "Auth", "probableRootCause": "Repeated pattern", "splunkQuerySuggestion": "index=logs", "recommendedSteps": "Apply patch", "confidence": "High", "isRepeatedIssue": true, "similarTicketReference": "001", "similarityScore": 0.85}'))]
        mock_client.chat.completions.create.return_value = mock_response

        analyzer = AIAnalyzer()
        hist_context = {"ticket_number": "001", "score": 0.85, "content": "Prev issue"}
        result = analyzer.analyze_ticket("Current issue content", historical_context=hist_context)
        
        self.assertTrue(result["isRepeatedIssue"])
        self.assertEqual(result["similarTicketReference"], "001")

if __name__ == '__main__':
    unittest.main()
