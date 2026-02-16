import unittest
from log_parser import LogParser

class TestLogParser(unittest.TestCase):
    def setUp(self):
        self.parser = LogParser()

    def test_parse_standard_errors(self):
        log_text = (
            "2026-02-17 14:31:02 ERROR service=AuthService env=PROD NullPointerException: User context missing\n"
            "2026-02-17 14:31:05 ERROR service=AuthService env=PROD NullPointerException: User context missing\n"
            "2026-02-17 14:32:10 WARN service=AuthService retrying...\n"
        )
        summary = self.parser.parse(log_text)
        
        self.assertEqual(summary["top_exception"], "NullPointerException")
        self.assertEqual(summary["exception_count"], 2)
        self.assertIn("AuthService", summary["detected_services"])
        self.assertIn("PROD", summary["environments"])
        self.assertEqual(summary["total_error_lines"], 2)

    def test_parse_kafka_timeout(self):
        log_text = (
            "2026-02-17T15:00:00Z FATAL KafkaTimeoutException: Failed to poll topic=orders after 5000ms\n"
            "2026-02-17T15:01:00Z FATAL KafkaTimeoutException: Failed to poll topic=orders after 5000ms\n"
        )
        summary = self.parser.parse(log_text)
        self.assertEqual(summary["top_exception"], "KafkaTimeoutException")
        self.assertEqual(summary["time_window"], "2026-02-17T15:00:00Z to 2026-02-17T15:01:00Z")

    def test_format_for_ai(self):
        summary = {
            "top_exception": "TimeoutException",
            "exception_count": 10,
            "total_error_lines": 15,
            "time_window": "10:00 to 11:00",
            "detected_services": ["PaymentSvc"],
            "environments": ["STAGING"],
            "dominant_patterns": ["Pattern A"]
        }
        text = self.parser.format_for_ai(summary)
        self.assertIn("TimeoutException", text)
        self.assertIn("PaymentSvc", text)

if __name__ == '__main__':
    unittest.main()
